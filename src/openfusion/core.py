"""The Fusion loop: a persistent lead (Claude Code) briefs a persistent sidekick via `fusion-delegate`,
then a fresh-context reviewer checks the result. Zero third-party dependencies."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

LEAD_RULES = """You are the LEAD of a Fusion team working in the current directory.
Teammates:
- SIDEKICK ({exec_spec}): does ALL implementation work (editing files, running commands, writing tests).
  Reach it with the shell command:   fusion-delegate "<brief>"
  The sidekick keeps its own persistent session across briefs, so later briefs can build on earlier ones.
- REVIEWER ({review_spec}): reviews the finished change with fresh context after you report DONE.
Rules:
- You never edit files yourself. You plan, brief, monitor, verify, and review.
- A brief states: objective, constraints, files/areas to touch, and success criteria (exact commands to
  run or tests that must pass). Keep briefs prescriptive for small models. The sidekick replies with a
  report of what changed and how it verified it.
- Read only what you need to plan and to verify the sidekick's claims; prefer targeted reads and `git diff`.
- {verify_line}
- If the sidekick fails a brief twice, make the brief more prescriptive or split it into smaller briefs.
- When the task is complete and verified, reply with a single line starting with  DONE:  and a one-sentence summary.
  If you cannot complete it, reply with a line starting with  BLOCKED:  and the exact blocker."""

SIDEKICK_NOTE = "The lead owns all task tracking and project management; do not create or update tracking issues."

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "request_changes"]},
        "summary": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "object", "properties": {
            "file": {"type": "string"}, "issue": {"type": "string"},
            "severity": {"type": "string", "enum": ["blocker", "major", "minor"]}},
            "required": ["file", "issue", "severity"], "additionalProperties": False}},
    },
    "required": ["verdict", "summary", "findings"], "additionalProperties": False,
}

REVIEW_PROMPT = """You are the REVIEWER in a Fusion team, with fresh context. You are READ-ONLY: do not modify,
create, or delete any files; do not run formatters or git write commands. {note}
Task that was assigned to the team:
{task}
Review the uncommitted change: run `git diff` (and `git status`), read what you need{verify}.
Approve only if the change fully solves the task, touches nothing it shouldn't, and verification passes.
Reply ONLY with JSON matching the schema (verdict, summary, findings)."""

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


@dataclass
class RunConfig:
    task: str
    cwd: Path
    lead: str = "claude:opus"
    exec_spec: str = "codex:gpt-5.6-luna"
    review: str | None = "codex:gpt-5.6-terra"
    test_cmd: str | None = None
    max_review_rounds: int = 1
    safe_mode: bool = True
    strict: bool = False
    budget_usd: float | None = None
    extra_allow: list[str] = field(default_factory=list)
    verbose: bool = False
    timeout: int = 3600


@dataclass
class Report:
    run_id: str
    config: dict
    started: float
    lead: dict = field(default_factory=dict)
    sidekick: list[dict] = field(default_factory=list)
    reviews: list[dict] = field(default_factory=list)
    final: str = ""
    wall_secs: float = 0.0

    def status(self) -> str:
        if self.final.startswith("BLOCKED"):
            return "blocked"
        if self.reviews and self.reviews[-1].get("verdict") != "approve":
            return "changes_requested"
        if "DONE" in self.final:
            return "done"
        return "unknown"


def sh(cmd: list[str], cwd: Path, env: dict, timeout: int) -> tuple[int, str, str, float]:
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)  # codex reads a piped stdin as prompt and blocks until EOF
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", f"timeout after {timeout}s", time.time() - t0


def load_dotenv(cwd: Path) -> None:
    """Load KEY=VALUE lines from ./.env (never overrides existing env)."""
    f = cwd / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def make_shim(state: Path) -> Path:
    """`fusion-delegate` must be callable by name from the lead's Bash tool. Provide a shim that runs
    this very interpreter's module, so it works from `uv tool install`, `pipx`, or a plain checkout."""
    binp = state / "bin"
    binp.mkdir(parents=True, exist_ok=True)
    shim = binp / "fusion-delegate"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" -m openfusion.delegate "$@"\n')
    shim.chmod(0o755)
    return binp


def parse_lead_stream(out: str, rep: Report, bash_cmds: list[str]) -> None:
    tools = rep.lead.setdefault("tools", {})
    for line in out.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "assistant":
            for b in e.get("message", {}).get("content", []):
                if b.get("type") == "tool_use":
                    name = b.get("name", "?")
                    if name == "Bash":
                        c = str(b.get("input", {}).get("command", ""))
                        bash_cmds.append(c)
                        name = "Bash(fusion-delegate)" if "fusion-delegate" in c else "Bash"
                    tools[name] = tools.get(name, 0) + 1
        elif e.get("type") == "result":
            rep.final = str(e.get("result", ""))
            rep.lead["cost_usd"] = round(rep.lead.get("cost_usd", 0.0) + (e.get("total_cost_usd") or 0.0), 4)
            rep.lead["turns"] = rep.lead.get("turns", 0) + (e.get("num_turns") or 0)
            if e.get("is_error"):
                rep.lead["error"] = rep.final[:500]
    rep.lead["edits"] = sum(v for k, v in tools.items() if k in EDIT_TOOLS)
    rep.lead["delegations"] = tools.get("Bash(fusion-delegate)", 0)


def run_review(cfg: RunConfig, state: Path, env: dict, log) -> dict:
    assert cfg.review
    rh, rm = cfg.review.split(":", 1)
    schema_path = state / "review-schema.json"
    schema_path.write_text(json.dumps(REVIEW_SCHEMA))
    verify = f", and run `{cfg.test_cmd}`" if cfg.test_cmd else ""
    prompt = REVIEW_PROMPT.format(task=cfg.task, verify=verify, note=SIDEKICK_NOTE)
    result: dict = {"spec": cfg.review}
    if rh == "codex":
        out_path = state / "review-last.json"
        out_path.unlink(missing_ok=True)
        rc, out, err, secs = sh(["codex", "exec", "--json", "--skip-git-repo-check", "-m", rm,
                                 "-c", 'approval_policy="never"', "--output-schema", str(schema_path),
                                 "-o", str(out_path), prompt], cfg.cwd, env, cfg.timeout)
        for line in out.splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("type") == "turn.completed":
                result["usage"] = e.get("usage", {})
            elif e.get("type") in ("error", "turn.failed"):
                result["error"] = json.dumps(e)[:500]
        try:
            result.update(json.loads(out_path.read_text()))
        except (OSError, json.JSONDecodeError):
            result.setdefault("verdict", "error")
            result.setdefault("summary", (result.get("error") or err or out).strip()[-400:])
    elif rh == "claude":
        cmd = ["claude", "-p", prompt, "--model", rm, "--output-format", "json", "--no-session-persistence",
               "--json-schema", json.dumps(REVIEW_SCHEMA),
               "--allowedTools", "Read,Grep,Glob,Bash(git diff *),Bash(git status *),Bash(git log *)"
               + (f",Bash({cfg.test_cmd}*)" if cfg.test_cmd else "")]
        if cfg.safe_mode:
            cmd.append("--safe-mode")
        rc, out, err, secs = sh(cmd, cfg.cwd, env, cfg.timeout)
        try:
            d = json.loads(out)
            v = d.get("structured_output") or json.loads(d.get("result", "{}"))
            result.update(v)
            result["usage"] = {"cost_usd": d.get("total_cost_usd"), "turns": d.get("num_turns")}
        except (json.JSONDecodeError, TypeError):
            result.update({"verdict": "error", "summary": (err or out).strip()[-400:]})
    else:
        secs = 0.0
        result.update({"verdict": "error", "summary": f"reviewer harness {rh!r} not supported (codex|claude)"})
    result["secs"] = round(secs, 1)
    log(f"review: {result.get('verdict')} — {str(result.get('summary', ''))[:140]}")
    return result


def run_task(cfg: RunConfig, log=print) -> Report:
    """Run one Fusion task in cfg.cwd. Returns the Report (also saved to .fusion/runs/<id>.json)."""
    lh, lm = cfg.lead.split(":", 1)
    if lh != "claude":
        raise SystemExit(f"lead harness {lh!r} not supported yet (claude only); executors/reviewers can be codex/claude/pi/grok")
    for binary in ("claude",):
        if not shutil.which(binary):
            raise SystemExit(f"{binary} not found on PATH; run `fusion doctor`")
    cfg.cwd = cfg.cwd.resolve()
    load_dotenv(cfg.cwd)
    state = cfg.cwd / ".fusion"
    runs = state / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    run_state = state / "state" / run_id
    run_state.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = f"{make_shim(state)}{os.pathsep}{env['PATH']}"
    env["FUSION_EXEC"] = cfg.exec_spec
    env["FUSION_STATE"] = str(run_state)
    session_id = str(uuid.uuid4())
    rep = Report(run_id=run_id, config={k: (str(v) if isinstance(v, Path) else v) for k, v in cfg.__dict__.items()},
                 started=time.time())
    bash_cmds: list[str] = []

    verify_line = f"Verify with:  {cfg.test_cmd}" if cfg.test_cmd else \
        "Verify by having the sidekick run the project's tests/build, and spot-check with `git diff`."
    rules = LEAD_RULES.format(exec_spec=cfg.exec_spec, review_spec=cfg.review or "none", verify_line=verify_line)
    allow = ["Read", "Grep", "Glob", "Bash(fusion-delegate *)", "Bash(git diff *)", "Bash(git status *)", "Bash(git log *)"]
    if cfg.test_cmd:
        allow.append(f"Bash({cfg.test_cmd}*)")
    allow += cfg.extra_allow

    def run_lead(prompt: str, resume: bool) -> None:
        # prompt right after -p: --allowedTools is variadic and would swallow a trailing prompt
        cmd = ["claude", "-p", prompt, "--model", lm, "--output-format", "stream-json", "--verbose",
               "--append-system-prompt", rules, "--allowedTools", ",".join(allow)]
        if cfg.safe_mode:
            cmd.append("--safe-mode")
        if cfg.strict:
            cmd += ["--disallowedTools", ",".join(EDIT_TOOLS)]
        if cfg.budget_usd:
            cmd += ["--max-budget-usd", str(cfg.budget_usd)]
        cmd += ["--resume", session_id] if resume else ["--session-id", session_id]
        rc, out, err, secs = sh(cmd, cfg.cwd, env, cfg.timeout)
        with (run_state / "lead.jsonl").open("a") as f:
            f.write(out + ("\n--- stderr ---\n" + err if err else "") + "\n")
        rep.lead["secs"] = round(rep.lead.get("secs", 0.0) + secs, 1)
        parse_lead_stream(out, rep, bash_cmds)
        if rc != 0 and not rep.final:
            rep.final = f"BLOCKED: lead exited {rc}: {(err or out).strip()[-300:]}"

    log(f"fusion run {run_id}  lead={cfg.lead}  sidekick={cfg.exec_spec}  reviewer={cfg.review or 'none'}")
    log(f"task: {cfg.task[:200]}")
    run_lead(cfg.task, resume=False)
    log(f"lead: {rep.final[:160]}")

    if cfg.review and "DONE" in rep.final:
        for round_no in range(cfg.max_review_rounds + 1):
            rv = run_review(cfg, run_state, env, log)
            rep.reviews.append(rv)
            if rv.get("verdict") != "request_changes" or round_no == cfg.max_review_rounds:
                break
            fb = ("REVIEWER FEEDBACK — address it via the sidekick, verify, then reply DONE: or BLOCKED:\n"
                  + json.dumps({"summary": rv.get("summary"), "findings": rv.get("findings")}, indent=1))
            run_lead(fb, resume=True)
            log(f"lead (after review {round_no + 1}): {rep.final[:160]}")

    dlog = run_state / "delegate.log"
    if dlog.exists():
        for line in dlog.read_text().splitlines():
            try:
                r = json.loads(line)
                rep.sidekick.append({"secs": r.get("secs"), "usage": r.get("usage"), "brief": str(r.get("brief", ""))[:200]})
            except json.JSONDecodeError:
                pass
    rep.lead["bash"] = bash_cmds[:20]
    rep.wall_secs = round(time.time() - rep.started, 1)
    (runs / f"{run_id}.json").write_text(json.dumps(rep.__dict__, indent=1, default=str))
    return rep


def format_report(rep: Report) -> str:
    L = rep.lead
    sk_cost = sum((s.get("usage") or {}).get("cost_usd") or 0.0 for s in rep.sidekick)
    sk_secs = sum(s.get("secs") or 0.0 for s in rep.sidekick)
    lines = [
        f"status: {rep.status()}   wall: {rep.wall_secs}s   run: {rep.run_id}",
        f"{'role':<10} {'spec':<34} {'time':>7}  detail",
        f"{'lead':<10} {rep.config['lead']:<34} {L.get('secs', 0):>6}s  turns={L.get('turns')} delegations={L.get('delegations')} edits={L.get('edits')} cost=${L.get('cost_usd', 0)}",
        f"{'sidekick':<10} {rep.config['exec_spec']:<34} {sk_secs:>6.1f}s  briefs={len(rep.sidekick)} cost=${sk_cost:.4f} (0 when the harness bills a subscription)",
    ]
    for i, rv in enumerate(rep.reviews, 1):
        u = rv.get("usage") or {}
        lines.append(f"{'review ' + str(i):<10} {rv.get('spec', ''):<34} {rv.get('secs', 0):>6}s  {rv.get('verdict')}: {str(rv.get('summary', ''))[:70]} {('tokens in=' + str(u.get('input_tokens'))) if u.get('input_tokens') else ''}")
    lines.append(f"final: {rep.final[:300]}")
    return "\n".join(lines)
