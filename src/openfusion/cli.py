"""fusion — Devin-Fusion-style orchestration on the AI subscriptions you already pay for.

  fusion "add rate limiting to /api/upload with tests"      run a task in the current repo
  fusion doctor                                              check harness installs / logins / keys
  fusion smoke                                               end-to-end check on a throwaway repo
  fusion review "the task"                                   fresh-context review of your current diff
  fusion runs                                                list past runs (.fusion/runs)

Roles: lead (plans/briefs/verifies), sidekick (implements), tester (e2e / computer-use, optional), reviewer (fresh-context verdict).
Role specs are  harness:model[@provider]  e.g. claude:opus, codex:gpt-5.6-luna, pi:z-ai/glm-5.3@openrouter.
Precedence: flags > FUSION_* env > ~/.config/fusion/config.toml [defaults] > built-ins.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import __version__
from .core import RunConfig, format_report, run_task
from .doctor import FAIL, format_rows, run_doctor

BUILTIN = {"lead": "claude:opus", "exec": "codex:gpt-5.6-luna", "review": "codex:gpt-5.6-terra", "tester": None, "test_cmd": None}
SUBCOMMANDS = {"run", "doctor", "smoke", "runs", "review"}


def load_config() -> dict:
    p = Path(os.environ.get("FUSION_CONFIG", Path.home() / ".config" / "fusion" / "config.toml"))
    if not p.exists():
        return {}
    try:
        import tomllib
        return tomllib.loads(p.read_text()).get("defaults", {})
    except Exception as e:  # noqa: BLE001
        print(f"warning: could not read {p}: {e}", file=sys.stderr)
        return {}


def defaults() -> dict:
    d = dict(BUILTIN)
    d.update({k: v for k, v in load_config().items() if k in d})
    for k, envk in (("lead", "FUSION_LEAD"), ("exec", "FUSION_EXEC"), ("review", "FUSION_REVIEW"),
                    ("tester", "FUSION_TESTER"), ("test_cmd", "FUSION_TEST_CMD")):
        if os.environ.get(envk):
            d[k] = os.environ[envk]
    return d


def add_role_flags(ap: argparse.ArgumentParser, d: dict) -> None:
    ap.add_argument("--lead", default=d["lead"], help=f"lead spec (default {d['lead']}); claude:* only for now")
    ap.add_argument("--exec", dest="exec_spec", default=d["exec"], help=f"sidekick spec (default {d['exec']})")
    ap.add_argument("--review", default=d["review"], help=f"reviewer spec or 'none' (default {d['review']})")
    ap.add_argument("--tester", default=d["tester"], help="tester spec for end-to-end / computer-use verification, e.g. codex:gpt-5.6-terra or claude:sonnet (default none)")


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in SUBCOMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "run")  # `fusion "task"` == `fusion run "task"`
    d = defaults()
    ap = argparse.ArgumentParser(prog="fusion", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"fusion {__version__}")
    sub = ap.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="run a task in the current repo (default)")
    r.add_argument("task", nargs="+", help="what to build/fix; quote it")
    add_role_flags(r, d)
    r.add_argument("--test-cmd", default=d["test_cmd"], help="verification command the lead may run, e.g. 'uv run pytest -q'")
    r.add_argument("--max-review-rounds", type=int, default=1)
    r.add_argument("--budget", type=float, default=None, help="max USD for the lead (Claude --max-budget-usd)")
    r.add_argument("--allow", action="append", default=[], help="extra Claude tool rule for the lead, e.g. 'Bash(npm test*)'")
    r.add_argument("--strict", action="store_true", help="also remove Edit/Write tools from the lead (default: prompt-only)")
    r.add_argument("--no-safe-mode", action="store_true", help="let the lead load your CLAUDE.md, hooks, skills, plugins")
    r.add_argument("--solo", action="store_true", help="baseline: lead does everything itself, no sidekick/reviewer")
    r.add_argument("-C", "--cwd", default=".")

    dc = sub.add_parser("doctor", help="check harness installs, logins, keys")
    dc.add_argument("--pi-model", default="z-ai/glm-5.3")
    dc.add_argument("--pi-provider", default="openrouter")

    sm = sub.add_parser("smoke", help="end-to-end check on a throwaway repo")
    add_role_flags(sm, d)
    sm.add_argument("--no-doctor", action="store_true")

    rv = sub.add_parser("review", help="fresh-context review of the current uncommitted diff against a task")
    rv.add_argument("task", nargs="+")
    rv.add_argument("--review", default=d["review"], help=f"reviewer spec (default {d['review']})")
    rv.add_argument("--test-cmd", default=d["test_cmd"])
    rv.add_argument("-C", "--cwd", default=".")

    ru = sub.add_parser("runs", help="list past runs in ./.fusion/runs")
    ru.add_argument("-C", "--cwd", default=".")

    a = ap.parse_args(argv)
    if a.cmd is None:
        ap.print_help()
        return

    if a.cmd == "doctor":
        from .core import load_dotenv
        load_dotenv(Path.cwd())
        rows = run_doctor(a.pi_model, a.pi_provider)
        print(format_rows(rows))
        sys.exit(1 if any(s == FAIL for _, s, _, _ in rows) else 0)

    if a.cmd == "smoke":
        from .core import load_dotenv
        from .smoke import run_smoke
        load_dotenv(Path.cwd())
        rows = []
        if not a.no_doctor:
            rows += run_doctor()
            print(format_rows(rows), "\n")
        review = None if a.review.lower() == "none" else a.review
        rows2 = run_smoke(a.lead, a.exec_spec, review)  # smoke has no tester (toy repo has nothing to drive)
        print("\n" + format_rows(rows2))
        fails = sum(1 for _, s, _, _ in rows + rows2 if s == FAIL)
        print(f"\n{len(rows) + len(rows2) - fails}/{len(rows) + len(rows2)} passed")
        sys.exit(1 if any(s == FAIL for _, s, _, _ in rows2) else 0)

    if a.cmd == "review":
        from .core import load_dotenv, run_review
        cwd = Path(a.cwd).resolve()
        load_dotenv(cwd)
        cfg = RunConfig(task=" ".join(a.task), cwd=cwd, review=a.review, test_cmd=a.test_cmd)
        state = cwd / ".fusion" / "state" / ("review-" + time.strftime("%Y%m%d-%H%M%S"))
        state.mkdir(parents=True, exist_ok=True)
        rv = run_review(cfg, state, dict(os.environ), print)
        print(json.dumps({k: rv.get(k) for k in ("verdict", "summary", "findings", "secs", "usage")}, indent=1))
        sys.exit(0 if rv.get("verdict") == "approve" else 1)

    if a.cmd == "runs":
        runs = sorted((Path(a.cwd) / ".fusion" / "runs").glob("*.json"))
        if not runs:
            print("no runs yet")
            return
        print(f"{'run':<24} {'status':<18} {'wall':>7} {'lead$':>7} {'briefs':>6}  task")
        for f in runs[-30:]:
            try:
                r = json.loads(f.read_text())
            except json.JSONDecodeError:
                continue
            final = r.get("final", "")
            status = "blocked" if final.startswith("BLOCKED") else ("done" if "DONE" in final else "unknown")
            if r.get("reviews") and r["reviews"][-1].get("verdict") != "approve":
                status = "changes_requested"
            print(f"{r['run_id']:<24} {status:<18} {r.get('wall_secs', 0):>6}s {r.get('lead', {}).get('cost_usd', 0):>7} {len(r.get('sidekick', [])):>6}  {r['config']['task'][:50]}")
        return

    # run
    review = None if (a.solo or a.review.lower() == "none") else a.review
    tester = None if (a.solo or not a.tester or a.tester.lower() == "none") else a.tester
    cfg = RunConfig(task=" ".join(a.task), cwd=Path(a.cwd), lead=a.lead, exec_spec=a.exec_spec, review=review,
                    tester=tester, test_cmd=a.test_cmd, max_review_rounds=a.max_review_rounds, safe_mode=not a.no_safe_mode,
                    strict=a.strict, budget_usd=a.budget, extra_allow=a.allow)
    if a.solo:
        cfg.exec_spec = "none"
    t0 = time.time()
    rep = run_task(cfg) if not a.solo else run_solo(cfg)
    print()
    print(format_report(rep))
    sys.exit(0 if rep.status() == "done" else 1)


def run_solo(cfg: RunConfig):
    """Baseline: the lead model does the task itself with full tools (what you'd get without Fusion)."""
    import subprocess
    from .core import Report, parse_lead_stream
    lh, lm = cfg.lead.split(":", 1)
    rep = Report(run_id=time.strftime("%Y%m%d-%H%M%S") + "-solo", config={**cfg.__dict__, "cwd": str(cfg.cwd)}, started=time.time())
    cmd = ["claude", "-p", cfg.task, "--model", lm, "--output-format", "stream-json", "--verbose",
           "--permission-mode", "acceptEdits", "--no-session-persistence"]
    if cfg.safe_mode:
        cmd.append("--safe-mode")
    if cfg.budget_usd:
        cmd += ["--max-budget-usd", str(cfg.budget_usd)]
    p = subprocess.run(cmd, cwd=str(cfg.cwd), text=True, capture_output=True, timeout=cfg.timeout, stdin=subprocess.DEVNULL)
    parse_lead_stream(p.stdout, rep, [])
    rep.lead["secs"] = round(time.time() - rep.started, 1)
    if "DONE" not in rep.final and rep.final:
        rep.final = "DONE: " + rep.final  # solo runs have no DONE protocol; count completion as done
    rep.wall_secs = rep.lead["secs"]
    runs = cfg.cwd / ".fusion" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{rep.run_id}.json").write_text(json.dumps(rep.__dict__, indent=1, default=str))
    return rep


if __name__ == "__main__":
    main()
