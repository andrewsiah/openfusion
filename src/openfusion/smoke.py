"""`fusion smoke`: end-to-end check on a throwaway repo with a failing test.
Pass = test green, lead delegated ≥1 brief, lead made 0 edits itself, lead said DONE, reviewer approved."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from .core import RunConfig, format_report, run_task
from .doctor import FAIL, PASS

TASK = ("The test suite in this repo fails. Get `python3 -m unittest -q` passing by fixing the bug "
        "in calc.py (do not change the tests).")


def make_repo(d: Path) -> None:
    (d / "calc.py").write_text("def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n")
    (d / "test_calc.py").write_text(
        "import unittest\nfrom calc import add, mul\n\n\nclass T(unittest.TestCase):\n"
        "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n"
        "    def test_mul(self):\n        self.assertEqual(mul(2, 3), 6)\n\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n")
    g = ["git", "-c", "user.name=smoke", "-c", "user.email=smoke@example.com"]
    subprocess.run(["git", "init", "-q"], cwd=d, check=False)
    subprocess.run(g + ["add", "-A"], cwd=d, check=False)
    subprocess.run(g + ["commit", "-qm", "seed"], cwd=d, check=False)


def run_smoke(lead: str, exec_spec: str, review: str | None, log=print) -> list[tuple[str, str, float | None, str]]:
    d = Path(tempfile.mkdtemp(prefix="fusion-smoke-"))
    make_repo(d)
    cfg = RunConfig(task=TASK, cwd=d, lead=lead, exec_spec=exec_spec, review=review,
                    test_cmd="python3 -m unittest -q", max_review_rounds=1)
    rep = run_task(cfg, log=log)
    log(format_report(rep))
    test_rc = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=d, capture_output=True).returncode
    extras = [l for l in subprocess.run(["git", "status", "--short"], cwd=d, capture_output=True, text=True).stdout.splitlines()
              if not l.endswith(("calc.py", ".fusion/", "__pycache__/"))]
    L = rep.lead
    rows = [
        ("tests green after run", PASS if test_rc == 0 else FAIL, None, f"unittest rc={test_rc}"),
        ("lead delegated", PASS if L.get("delegations", 0) >= 1 else FAIL, None, f"fusion-delegate calls={L.get('delegations')}"),
        ("lead made no edits", PASS if L.get("edits", 0) == 0 else FAIL, None, f"edit tool calls={L.get('edits')} tools={L.get('tools')}"),
        ("lead reported DONE", PASS if "DONE" in rep.final else FAIL, L.get("secs"), f"turns={L.get('turns')} cost=${L.get('cost_usd')}"),
        ("sidekick ran", PASS if rep.sidekick else FAIL, sum(s.get("secs") or 0 for s in rep.sidekick) or None,
         f"briefs={len(rep.sidekick)} usage={rep.sidekick[-1]['usage'] if rep.sidekick else 'none'}"),
        ("only calc.py changed", PASS if not extras else FAIL, None, f"extras={extras}"),
    ]
    if review:
        rv = rep.reviews[-1] if rep.reviews else {}
        rows.append(("reviewer approved", PASS if rv.get("verdict") == "approve" else FAIL, rv.get("secs"),
                     f"{review} rounds={len(rep.reviews)} verdicts={[r.get('verdict') for r in rep.reviews]}"))
    log(f"repo kept for inspection: {d}")
    return rows
