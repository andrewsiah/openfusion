# OpenFusion

**Devin-Fusion-style orchestration on the AI subscriptions you already pay for.**

```bash
uv tool install openfusion
fusion "add rate limiting to /api/upload with tests"
```

A frontier model (your Claude Max **Fable/Opus** or ChatGPT **Astra**) plans, briefs, monitors and reviews. A cheap, fast model (**GPT-5.6 Luna**, **Haiku**, or **GLM / Grok / Kimi / DeepSeek via OpenRouter**) does the typing. You get frontier-quality judgment at a fraction of the tokens and wall-clock, without a new API bill.

> Status: research + plan stage. No code yet. See [PLAN.md](PLAN.md).

## Why

[Cognition's Devin Fusion](https://cognition.com/blog/devin-fusion) showed that a persistent frontier "lead" that only plans and reviews, paired with a persistent cheap "sidekick" that executes, cuts cost 23–46% at roughly equal quality. The insight: the smart model should be the *planner*, not the *typist*, and the two should exchange **briefs and results**, not whole conversations.

Most of us already pay for Claude and/or ChatGPT, and the CLIs for both (`claude`, `codex`) are excellent harnesses. OpenFusion doesn't build a new harness. It spawns the **unmodified** binaries you're already logged into, assigns each a role, and wires them together with a local MCP `delegate` tool. Executors can also be any model behind your own OpenRouter key via OpenCode.

## How it works

```
fusion "task"
  ├─ Lead      claude:fable        persistent, role prompt + delegate() tool   plans, briefs, reviews
  ├─ Sidekick  codex:gpt-5.6-luna  persistent session resumed per brief       edits, runs tests, reports
  ├─ Reviewer  codex:gpt-6-astra   fresh context, read-only                   approve / request changes
  └─ Report    wall-clock + per-role cost
```

Roles are `harness:model[@provider]` specs. Presets:

| Preset | Lead | Executor | Reviewer |
|---|---|---|---|
| `dual` | `claude:fable` | `codex:gpt-5.6-luna` | `codex:gpt-6-astra` |
| `claude` | `claude:fable` | `claude:haiku` | `claude:opus` |
| `codex` | `codex:gpt-6-astra` | `codex:gpt-5.6-luna` | `codex:gpt-6-astra` |
| `openrouter` | `claude:fable` | `opencode:z-ai/glm-5.3@openrouter` | `claude:opus` |
| `byok` | `opencode:…@openrouter` | `opencode:…@openrouter` | `opencode:…@openrouter` |

```bash
fusion init                                   # detect logins, pick a preset
fusion -p openrouter "…"
fusion --lead claude:fable --exec opencode:x-ai/grok-4.6@openrouter "…"
fusion --solo "…"                             # baseline: lead does everything
fusion runs                                   # cost / time history
```

## Subscription usage and terms

OpenFusion never reads, stores, or proxies your Claude or ChatGPT credentials. It runs the vendors' own unmodified CLIs, which you log into yourself. Usage still counts against your plan limits. Anthropic's terms say plan limits "assume ordinary, individual usage of Claude Code" and reserve enforcement rights; if that's a concern, point the lead at an API key or a different vendor with one flag. Details in [docs/research/harnesses.md](docs/research/harnesses.md).

## Smoke test (prototype)

Before there is a real `fusion` CLI, `scripts/` holds a two-file prototype of the core loop so you can check your machine is ready:

- `scripts/fusion-delegate` — the `delegate` tool as a plain shell command. Hands a brief to a persistent sidekick session and prints its report plus usage. Harnesses: `codex` (ChatGPT login), `claude` (Claude login), `grok` (grok.com login), and `pi` for any bring-your-own-key model, e.g. `pi:z-ai/glm-5.3@openrouter`. Pi is [badlogic's pi-coding-agent](https://www.npmjs.com/package/@mariozechner/pi-coding-agent) (`npm i -g @mariozechner/pi-coding-agent`); it reads `OPENROUTER_API_KEY`, `XAI_API_KEY`, `GROQ_API_KEY`, `ZAI_API_KEY` etc. from env or the repo's gitignored `.env`.
- `scripts/smoke.py` — Part 1 pings each installed harness on your own login or key. Part 2 seeds a throwaway repo with a failing test and runs a lead (`claude:sonnet` by default) that is told, by prompt only, to fix it via `fusion-delegate`. Part 3 runs a fresh-context reviewer (`codex:gpt-5.6-terra` by default) that returns a JSON verdict; one `request_changes` round is fed back to the lead. Passes when the test is green, the lead delegated at least once, the lead made zero edits itself, and the reviewer approved.

```bash
python3 scripts/smoke.py                                  # everything, ~1–2 min
python3 scripts/smoke.py --only harnesses
python3 scripts/smoke.py --only loop --lead claude:opus --exec codex:gpt-5.6-terra --review none
python3 scripts/smoke.py --only loop --lead claude:opus --exec pi:z-ai/glm-5.3@openrouter --review codex:gpt-5.6-terra
```

Verified 2026-09-14 on one Linux VM: Opus lead + Codex Terra sidekick (5/5), and Opus lead + Pi sidekick on an OpenRouter model + Codex Terra reviewer (7/7, 66s, lead $0.22, sidekick $0.01, reviewer ~106k tokens of which 77k cached).

Notes from the first runs: the lead is started with `--safe-mode` so your personal `CLAUDE.md`, skills and hooks don't leak into the role; Codex inherits your `~/.codex/config.toml` sandbox setting (its bubblewrap sandbox does not work on every Linux VM); Codex still reads your global `~/.codex/AGENTS.md`, so the sidekick and reviewer prompts say the lead owns task tracking; Pi runs with `--no-context-files` for the same reason. Pointing Claude Code itself at OpenRouter's Anthropic-compatible endpoint did not work for non-Anthropic models (401 loop), which is why BYOK models go through Pi. OpenAI strict JSON schemas need every property in `required`.

## Research

- [docs/research/devin-fusion.md](docs/research/devin-fusion.md) — what Cognition actually published, numbers, related work, OSS landscape
- [docs/research/harnesses.md](docs/research/harnesses.md) — Claude Code / Codex / OpenCode headless interfaces, auth rules, routing to open models, Sept 2026 pricing

## License

MIT
