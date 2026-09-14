"""`fusion doctor`: is each harness installed and logged in / keyed? One tiny prompt per harness."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


def _sh(cmd: list[str], timeout: int = 120) -> tuple[int, str, str, float]:
    t0 = time.time()
    try:
        p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", f"timeout after {timeout}s", time.time() - t0


def check_claude(model: str = "haiku") -> tuple[str, str, float | None, str]:
    if not shutil.which("claude"):
        return f"claude", SKIP, None, "not installed: npm i -g @anthropic-ai/claude-code ; then run `claude` once to log in"
    rc, out, err, secs = _sh(["claude", "-p", "Reply with exactly: OK", "--model", model, "--output-format", "json",
                              "--no-session-persistence", "--safe-mode"])
    try:
        d = json.loads(out)
        ok = "OK" in str(d.get("result", "")) and not d.get("is_error")
        return f"claude:{model}", PASS if ok else FAIL, secs, f"result={str(d.get('result'))[:40]!r} cost=${d.get('total_cost_usd')}"
    except json.JSONDecodeError:
        return f"claude:{model}", FAIL, secs, (err or out).strip()[:200] or "no output (not logged in? run `claude`)"


def check_codex(model: str = "gpt-5.6-luna") -> tuple[str, str, float | None, str]:
    if not shutil.which("codex"):
        return "codex", SKIP, None, "not installed: npm i -g @openai/codex ; then `codex login`"
    rc, out, err, secs = _sh(["codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
                              "-m", model, "Reply with exactly: OK"])
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
        return f"codex:{model}", PASS, secs, f"result={text!r} in={usage.get('input_tokens')} cached={usage.get('cached_input_tokens')}"
    return f"codex:{model}", FAIL, secs, (" | ".join(errs) or err or out).strip()[:200] or "no output (run `codex login`)"


def check_grok(model: str = "grok-4.6") -> tuple[str, str, float | None, str]:
    if not shutil.which("grok"):
        return "grok", SKIP, None, "not installed (xAI Grok Build CLI)"
    rc, out, err, secs = _sh(["grok", "-p", "Reply with exactly: OK", "-m", model, "--output-format", "json"], 90)
    if rc == 0 and "OK" in out:
        return f"grok:{model}", PASS, secs, out.strip().replace("\n", " ")[:100]
    msg = ""
    for line in out.splitlines():
        try:
            e = json.loads(line)
            if e.get("type") == "error":
                msg = e.get("message", "")
        except json.JSONDecodeError:
            pass
    return f"grok:{model}", FAIL, secs, (msg or err or out).strip().replace("\n", " ")[:200]


def check_pi(model: str = "z-ai/glm-5.3", provider: str = "openrouter") -> tuple[str, str, float | None, str]:
    spec = f"pi:{model}@{provider}"
    if not shutil.which("pi"):
        return "pi", SKIP, None, "not installed: npm i -g @mariozechner/pi-coding-agent"
    key_env = {"openrouter": "OPENROUTER_API_KEY", "xai": "XAI_API_KEY", "groq": "GROQ_API_KEY",
               "zai": "ZAI_API_KEY", "cerebras": "CEREBRAS_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}.get(provider)
    if key_env and not os.environ.get(key_env):
        return spec, SKIP, None, f"{key_env} not set (export it or put it in ./.env)"
    rc, out, err, secs = _sh(["pi", "-p", "--model", f"{provider}/{model}", "--mode", "json", "--no-session",
                              "--no-context-files", "--no-extensions", "--no-skills", "--no-prompt-templates",
                              "--no-tools", "Reply with exactly: OK"])
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
        return spec, PASS, secs, f"result={text.strip()!r} cost=${(usage.get('cost') or {}).get('total')}"
    hint = "  (hint: set FUSION_PI_MAX_TOKENS=4096 or top up)" if "fewer max_tokens" in errmsg else ""
    return spec, FAIL, secs, ((errmsg or err or out).strip().replace("\n", " ")[:180]) + hint


def run_doctor(pi_model: str = "z-ai/glm-5.3", pi_provider: str = "openrouter") -> list[tuple[str, str, float | None, str]]:
    return [check_claude(), check_codex(), check_grok(), check_pi(pi_model, pi_provider)]


def format_rows(rows: list[tuple[str, str, float | None, str]]) -> str:
    out = [f"{'check':<30} {'status':<6} {'time':<7} detail"]
    for c, s, t, d in rows:
        out.append(f"{c:<30} {s:<6} {(f'{t:.1f}s' if t is not None else '-'):<7} {d[:100]}")
    return "\n".join(out)
