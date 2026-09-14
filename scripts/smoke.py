#!/usr/bin/env python3
"""OpenFusion smoke test.

Part 1  Each installed harness answers a one-line prompt headlessly on your own login
        (claude / codex / grok). Reports latency, model, cost or tokens.
Part 2  Minimal Fusion loop on a throwaway repo: a lead (Claude) is told, by prompt only,
        that its sidekick handles implementation and must be reached via `fusion-delegate`.
        The repo has a failing test; pass = test green afterwards, lead made zero edits
        itself, delegate was called at least once.

Part 3  (with --review) a fresh-context reviewer (Codex Terra by default) checks the diff and tests
        and returns a JSON verdict; one request_changes round is fed back to the lead.

Usage:  python3 scripts/smoke.py [--lead claude:sonnet] [--exec codex:gpt-5.6-luna] [--review codex:gpt-5.6-terra|none]
Env:    FUSION_LEAD / FUSION_EXEC / FUSION_REVIEW override the defaults above; OPENROUTER_API_KEY (or repo .env) for pi.
Requires only python3 and the harness CLIs; no pip installs.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Load repo-root .env (gitignored) so BYOK keys like OPENROUTER_API_KEY reach Pi.
_envf = ROOT.parent / ".env"
if _envf.exists():
    for _l in _envf.read_text().splitlines():
        if "=" in _l and not _l.lstrip().startswith("#"):
            _k, _v = _l.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
rows: list[tuple[str, str, str, str]] = []  # (check, status, timing, detail)


def row(check: str, status: str, secs: float | None, detail: str) -> None:
    rows.append((check, status, f"{secs:.1f}s" if secs is not None else "-", detail[:90]))
    print(f"  [{status}] {check:<28} {detail[:110]}")


def sh(cmd: list[str], cwd: str | None = None, env: dict | None = None, timeout: int = 180) -> tuple[int, str, str, float]:
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", f"timeout after {timeout}s", time.time() - t0


# ---------- Part 1: harness one-liners ----------

def check_claude(model: str) -> None:
    if not shutil.which("claude"):
        return row("claude", SKIP, None, "binary not found")
    rc, out, err, secs = sh(["claude", "-p", "--model", model, "--output-format", "json",
                             "--no-session-persistence", "Reply with exactly: OK"])
    try:
        d = json.loads(out)
        ok = "OK" in str(d.get("result", ""))
        models = ",".join((d.get("modelUsage") or {}).keys())
        row(f"claude:{model}", PASS if ok else FAIL, secs,
            f"result={d.get('result')!r} cost=${d.get('total_cost_usd')} model={models}")
    except json.JSONDecodeError:
        row(f"claude:{model}", FAIL, secs, (err or out).strip()[:200])


def check_codex(model: str) -> None:
    if not shutil.which("codex"):
        return row("codex", SKIP, None, "binary not found")
    rc, out, err, secs = sh(["codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
                             "-s", "read-only", "-m", model, "Reply with exactly: OK"])
    text, usage, errs = "", {}, []
    for line in out.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message":
            text += e["item"].get("text", "")
        elif e.get("type") == "turn.completed":
            usage = e.get("usage", {})
        elif e.get("type") == "error":
            errs.append(e.get("message", ""))
    if "OK" in text:
        row(f"codex:{model}", PASS, secs, f"result={text!r} in={usage.get('input_tokens')} "
            f"cached={usage.get('cached_input_tokens')} out={usage.get('output_tokens')}")
    else:
        row(f"codex:{model}", FAIL, secs, (" | ".join(errs) or err or out).strip()[:200])


def check_grok(model: str) -> None:
    if not shutil.which("grok"):
        return row("grok", SKIP, None, "binary not found")
    rc, out, err, secs = sh(["grok", "-p", "Reply with exactly: OK", "-m", model, "--output-format", "json"], timeout=90)
    if rc == 0 and "OK" in out:
        row(f"grok:{model}", PASS, secs, out.strip().replace("\n", " ")[:120])
    else:
        msg = ""
        for line in out.splitlines():
            try:
                e = json.loads(line)
                if e.get("type") == "error":
                    msg = e.get("message", "")
            except json.JSONDecodeError:
                pass
        row(f"grok:{model}", FAIL, secs, (msg or err or out).strip().replace("\n", " ")[:200])


def check_pi(model: str) -> None:
    if not shutil.which("pi"):
        return row("pi", SKIP, None, "binary not found (npm i -g @mariozechner/pi-coding-agent)")
    if not os.environ.get("OPENROUTER_API_KEY"):
        return row(f"pi:{model}", SKIP, None, "OPENROUTER_API_KEY not set")
    rc, out, err, secs = sh(["pi", "-p", "--model", f"openrouter/{model}", "--mode", "json", "--no-session",
                             "--no-context-files", "--no-extensions", "--no-skills", "--no-prompt-templates",
                             "--no-tools", "Reply with exactly: OK"], timeout=120)
    text, usage, errmsg = "", {}, ""
    for line in out.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "message_end" and e.get("message", {}).get("role") == "assistant":
            m = e["message"]
            text += "".join(b.get("text", "") for b in m.get("content", []) if b.get("type") == "text")
            usage = m.get("usage") or {}
            errmsg = m.get("errorMessage", "") or errmsg
    if "OK" in text:
        row(f"pi:{model}@openrouter", PASS, secs, f"result={text.strip()!r} in={usage.get('input')} out={usage.get('output')} cost=${(usage.get('cost') or {}).get('total')}")
    else:
        row(f"pi:{model}@openrouter", FAIL, secs, (errmsg or err or out).strip().replace("\n", " ")[:200])


# ---------- Part 2: minimal Fusion loop ----------

LEAD_RULES = """You are the LEAD in a Fusion pair working in the current directory.
Your teammate is a SIDEKICK agent ({exec_spec}) that does all implementation work.
Rules:
- You never edit files yourself. You plan, brief, verify, and review.
- To delegate, run exactly:  fusion-delegate "<brief>"   (a shell command). Put the objective,
  constraints, and success criteria in the brief. The sidekick replies with a report.
- Read only what you need to plan and to verify the sidekick's claims.
- Verify with:  python3 -m unittest -q
- When the task is complete, reply with a single line starting with DONE: and a one-sentence summary."""

TASK = ("The test suite in this repo fails. Get `python3 -m unittest -q` passing by fixing the bug "
        "in calc.py (do not change the tests).")


def make_repo(d: Path) -> None:
    (d / "calc.py").write_text("def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n")
    (d / "test_calc.py").write_text(
        "import unittest\nfrom calc import add, mul\n\n\nclass T(unittest.TestCase):\n"
        "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n"
        "    def test_mul(self):\n        self.assertEqual(mul(2, 3), 6)\n\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n")
    subprocess.run(["git", "init", "-q"], cwd=d, check=False)
    subprocess.run(["git", "-c", "user.name=smoke", "-c", "user.email=smoke@example.com",
                    "add", "-A"], cwd=d, check=False)
    subprocess.run(["git", "-c", "user.name=smoke", "-c", "user.email=smoke@example.com",
                    "commit", "-qm", "seed"], cwd=d, check=False)


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
create, or delete any files; do not run formatters or git write commands. The lead owns all task
tracking (issue trackers, tickets); do not create or update any tracking issues or notes.
Task that was assigned to the team: {task}
Review the uncommitted change: run `git diff`, read what you need, run `python3 -m unittest -q`.
Approve only if the change fully solves the task, touches nothing it shouldn't, and tests pass.
Reply ONLY with JSON matching the schema (verdict, summary, findings)."""


def review(review_spec: str, d: Path, env: dict) -> tuple[dict, float, str]:
    """Fresh-context reviewer. Returns (verdict_json, secs, usage_str)."""
    rh, rm = review_spec.split(":", 1)
    schema_path = d / ".fusion" / "review-schema.json"
    schema_path.write_text(json.dumps(REVIEW_SCHEMA))
    prompt = REVIEW_PROMPT.format(task=TASK)
    if rh == "codex":
        out_path = d / ".fusion" / "review-last.json"
        rc, out, err, secs = sh(["codex", "exec", "--json", "--skip-git-repo-check", "-m", rm,
                                 "-c", 'approval_policy="never"', "--output-schema", str(schema_path),
                                 "-o", str(out_path), prompt], cwd=str(d), env=env, timeout=600)
        usage = ""
        for line in out.splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("type") == "turn.completed":
                u = e.get("usage", {})
                usage = f"in={u.get('input_tokens')} cached={u.get('cached_input_tokens')} out={u.get('output_tokens')}"
        try:
            return json.loads(out_path.read_text()), secs, usage
        except (OSError, json.JSONDecodeError):
            return {"verdict": "error", "summary": (err or out).strip()[-300:], "findings": []}, secs, usage
    if rh == "claude":
        rc, out, err, secs = sh(["claude", "-p", prompt, "--model", rm, "--output-format", "json",
                                 "--no-session-persistence", "--safe-mode",
                                 "--json-schema", json.dumps(REVIEW_SCHEMA),
                                 "--allowedTools", "Read,Grep,Glob,Bash(git diff *),Bash(python3 -m unittest*)"],
                                cwd=str(d), env=env, timeout=600)
        try:
            dd = json.loads(out)
            v = dd.get("structured_output") or json.loads(dd.get("result", "{}"))
            return v, secs, f"cost=${dd.get('total_cost_usd')} turns={dd.get('num_turns')}"
        except (json.JSONDecodeError, TypeError):
            return {"verdict": "error", "summary": (err or out).strip()[-300:], "findings": []}, secs, ""
    return {"verdict": "error", "summary": f"reviewer harness {rh!r} not supported", "findings": []}, 0.0, ""


def loop(lead_spec: str, exec_spec: str, review_spec: str | None) -> None:
    lh, lm = lead_spec.split(":", 1)
    if lh != "claude":
        return row("fusion loop", SKIP, None, f"lead harness {lh!r} not supported by smoke yet (claude only)")
    d = Path(tempfile.mkdtemp(prefix="fusion-smoke-"))
    make_repo(d)
    (d / ".fusion").mkdir(exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = f"{ROOT}{os.pathsep}{env['PATH']}"
    env["FUSION_EXEC"] = exec_spec
    env["FUSION_STATE"] = str(d / ".fusion")
    session_id = str(uuid.uuid4())

    def run_lead(prompt: str, resume: bool) -> tuple[str, str, float]:
        # prompt goes right after -p: --allowedTools is variadic and would swallow a trailing prompt
        # --safe-mode: no user CLAUDE.md / skills / hooks / plugins leaking into the lead; auth still works
        cmd = ["claude", "-p", prompt, "--model", lm, "--output-format", "stream-json", "--verbose", "--safe-mode",
               "--append-system-prompt", LEAD_RULES.format(exec_spec=exec_spec),
               "--allowedTools", "Read,Grep,Glob,Bash(fusion-delegate *),Bash(python3 -m unittest*),Bash(git diff *),Bash(git status *)"]
        cmd += ["--resume", session_id] if resume else ["--session-id", session_id]
        rc, out, err, secs = sh(cmd, cwd=str(d), env=env, timeout=600)
        with (d / ".fusion" / "lead.jsonl").open("a") as f:
            f.write(out + ("\n--- stderr ---\n" + err if err else "") + "\n")
        return out, err, secs

    print(f"\n  lead={lead_spec} sidekick={exec_spec} reviewer={review_spec or '-'} repo={d}")
    out, err, secs = run_lead(TASK, resume=False)
    tools: dict[str, int] = {}
    bash_cmds: list[str] = []
    final, cost, turns = "", 0.0, 0

    def ingest(out: str) -> None:
        nonlocal final, cost, turns
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
                            bash_cmds.append(c[:80])
                            name = "Bash(fusion-delegate)" if "fusion-delegate" in c else "Bash(other)"
                        tools[name] = tools.get(name, 0) + 1
            elif e.get("type") == "result":
                final = str(e.get("result", ""))
                cost += e.get("total_cost_usd") or 0.0
                turns += e.get("num_turns") or 0

    ingest(out)

    verdicts: list[str] = []
    review_secs, review_usage = 0.0, ""
    if review_spec:
        v, rs, review_usage = review(review_spec, d, env)
        review_secs += rs
        verdicts.append(v.get("verdict", "error"))
        print(f"  review 1: {v.get('verdict')} — {str(v.get('summary'))[:120]}")
        if v.get("verdict") == "request_changes":
            fb = "REVIEWER FEEDBACK (address via the sidekick, then verify and reply DONE):\n" + \
                 json.dumps({"summary": v.get("summary"), "findings": v.get("findings")}, indent=1)
            out2, err2, secs2 = run_lead(fb, resume=True)
            secs += secs2
            ingest(out2)
            v2, rs2, review_usage = review(review_spec, d, env)
            review_secs += rs2
            verdicts.append(v2.get("verdict", "error"))
            print(f"  review 2: {v2.get('verdict')} — {str(v2.get('summary'))[:120]}")

    test_rc = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=d, capture_output=True).returncode
    lead_edits = sum(v for k, v in tools.items() if k in ("Edit", "Write", "MultiEdit", "NotebookEdit"))
    delegations = tools.get("Bash(fusion-delegate)", 0)
    log = d / ".fusion" / "delegate.log"
    sk_usage = []
    if log.exists():
        for line in log.read_text().splitlines():
            try:
                r = json.loads(line)
                sk_usage.append(f"{r['secs']}s {json.dumps(r['usage'])}")
            except (json.JSONDecodeError, KeyError):
                pass
    reviewer_wrote = subprocess.run(["git", "status", "--short"], cwd=d, capture_output=True, text=True).stdout
    unexpected = [l for l in reviewer_wrote.splitlines() if not l.endswith(("calc.py", ".fusion/", "__pycache__/"))]

    row("tests green after run", PASS if test_rc == 0 else FAIL, None, f"unittest rc={test_rc}")
    row("lead delegated", PASS if delegations >= 1 else FAIL, None,
        f"fusion-delegate calls={delegations}; bash={bash_cmds[:4]}")
    row("lead made no edits", PASS if lead_edits == 0 else FAIL, None, f"lead edit tool calls={lead_edits} tools={tools}")
    row("lead reported DONE", PASS if "DONE" in final else FAIL, secs,
        f"cost=${cost:.4f} turns={turns} final={final[:60]!r}")
    row("sidekick usage", PASS if sk_usage else FAIL, None, "; ".join(sk_usage)[:120] or (err.strip()[:120] if err else "no delegate.log"))
    if review_spec:
        row("reviewer verdict", PASS if verdicts and verdicts[-1] == "approve" else FAIL, review_secs,
            f"{review_spec} rounds={len(verdicts)} verdicts={verdicts} {review_usage}")
        row("only calc.py changed", PASS if not unexpected else FAIL, None, f"git status extras={unexpected}")
    print(f"  repo kept for inspection: {d}")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead", default=os.environ.get("FUSION_LEAD", "claude:sonnet"))
    ap.add_argument("--exec", dest="exec_spec", default=os.environ.get("FUSION_EXEC", "codex:gpt-5.6-luna"))
    ap.add_argument("--review", dest="review_spec", default=os.environ.get("FUSION_REVIEW", "codex:gpt-5.6-terra"),
                    help="reviewer spec, or 'none'")
    ap.add_argument("--grok-model", default="grok-4.6")
    ap.add_argument("--pi-model", default="z-ai/glm-5.3", help="OpenRouter model id for the Pi one-liner check")
    ap.add_argument("--skip-loop", action="store_true")
    ap.add_argument("--only", choices=["harnesses", "loop"])
    a = ap.parse_args()

    t0 = time.time()
    if a.only != "loop":
        print("Part 1: harness one-liners on your own logins")
        check_claude("haiku")
        check_codex("gpt-5.6-luna")
        check_grok(a.grok_model)
        check_pi(a.pi_model)
    if a.only != "harnesses" and not a.skip_loop:
        print("\nPart 2: minimal Fusion loop (lead by prompt only, sidekick via fusion-delegate)")
        loop(a.lead, a.exec_spec, None if a.review_spec.lower() == "none" else a.review_spec)

    print(f"\n{'check':<28} {'status':<6} {'time':<8} detail")
    for c, s, t, dt in rows:
        print(f"{c:<28} {s:<6} {t:<8} {dt}")
    fails = sum(1 for r in rows if r[1] == FAIL)
    print(f"\n{len(rows) - fails}/{len(rows)} passed in {time.time() - t0:.0f}s")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
