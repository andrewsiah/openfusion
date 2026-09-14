# OpenFusion — Plan

> Devin-Fusion-style orchestration for people who already pay for Claude and ChatGPT.
> One command: `fusion "add rate limiting to the API"`. A frontier model plans, briefs, and reviews. A cheap, fast model does the typing. You pay with the subscriptions you already have, or bring an OpenRouter key.

Status: **plan + research complete, no code yet** (2026-09-14). Tracking: Linear [AND-85](https://linear.app/new-york-ai-labs/issue/AND-85).

---

## 0. TL;DR

- **What Fusion actually is** (from Cognition's posts, see [docs/research/devin-fusion.md](docs/research/devin-fusion.md)): a *persistent* frontier "lead" that only plans, briefs, monitors and reviews, plus a *persistent* cheap "sidekick" agent with its own tools and its own cached context. They exchange **briefs, results and feedback**, never whole conversations. Cognition reports 23–46% lower cost at roughly equal quality (Fable 5.1 + SWE-2 vs Fable 5.1 solo), and explicitly says the quality win comes from the frontier model being the *planner*, not the *typist*.
- **What you do today by hand** ("Fable, you orchestrate, use sub-agents to execute, use Astra to review") is the right idea but not Fusion-native: the sub-agents are the same vendor, the lead still reads and edits freely, there's no persistent sidekick, no cross-vendor review, and no cost accounting.
- **The Pareto-frontier design**: don't build a new harness. Build a thin orchestrator that spawns the harnesses people already have logged in (**unmodified `claude`, `codex`, `opencode` binaries**), assigns each a role, and wires them together with a local MCP "delegate" tool. That keeps subscription auth legal, inherits every harness's tools/sandboxing/caching, and makes the executor model a config value.
- **Roles → harness:model.** Lead = `claude:fable` or `codex:gpt-6-astra` on your subscription. Executor = `codex:gpt-5.6-luna` (ChatGPT sub), `claude:haiku` (Claude sub), or `opencode:z-ai/glm-5.3` (OpenRouter key). Reviewer = fresh-context frontier session, ideally the *other* vendor.
- **Ship as** a Python 3.12 package on PyPI (`uv tool install openfusion` / `uvx openfusion`), CLI name `fusion`. MIT. Private repo while we dogfood, public after Phase 2.

---

## 1. Goals and non-goals

### Goals
1. **Use what people already pay for.** Zero new API bills for the lead. Claude Pro/Max/Team and ChatGPT Plus/Pro users should be productive within two minutes of install.
2. **Speed and cost first, without a quality cliff.** Cheap/fast executors (Luna, Haiku, GLM, Grok, Kimi, DeepSeek) do the bulk of tokens; the frontier model spends tokens only on planning, ambiguity, and review.
3. **Bring your own key for executors/reviewers.** OpenRouter (or any Anthropic-/Responses-compatible endpoint) plugs in as a first-class option.
4. **Fusion-native, not "sub-agents with a hat on".** Persistent lead and sidekick contexts; brief/result exchange; hands-off lead; fresh-context review; escalation when the sidekick struggles; per-task cost + wall-clock report.
5. **Lightweight and minimally invasive.** One package, no daemon, no database, no cloud. The harnesses run unmodified; `fusion` adds exactly two things per invocation: a role prompt and a `delegate` tool. Config is one TOML file.
6. **Open and contributable.** Adding a harness or preset is one small file.

### Non-goals (for now)
- Not a new agent harness. We never implement our own tool loop, file editing, or sandbox. We compose existing harnesses.
- Not a proxy for subscription credentials. We never read, store, or forward OAuth tokens (see §4).
- Not a swarm. Single writer at a time by default (Cognition: "parallel-writer swarms don't work"). Parallel sidekicks in worktrees are Phase 3+.
- Not a router that picks a model per prompt. Fusion's insight is that one-shot routing fails; the lead decides dynamically per subtask.

---

## 2. What we learned (research summary)

Full briefings: [docs/research/devin-fusion.md](docs/research/devin-fusion.md), [docs/research/harnesses.md](docs/research/harnesses.md).

### Fusion's design principles (Cognition, quoted or closely paraphrased)
1. Lead and sidekick are **both fully capable agents** with their own tools and context; they run in parallel.
2. The lead should "**delegate and monitor**", "take minimal actions, and only read what is absolutely necessary", keeping "the plan, the interpretation of ambiguity, the final review".
3. The lead hands the sidekick a **brief with constraints and success criteria**; they only exchange briefs, results and feedback. This is what keeps both prompt caches warm (their critique of "advisor"/"smart friend" designs is cache economics).
4. **Weaker sidekick → more prescriptive briefs**, less room to push back. "Exploration needed for planning should not be delegated to a weaker sidekick."
5. **Switching is dynamic** (lightweight classifiers during execution), applied at compaction points where the cache would miss anyway.
6. **Measure price per task, not per token.** SWE-2 ($0.75/M) beat Luna ($0.20/M) on cost per task because it needed fewer turns.
7. Known failure mode: delegation loses "subtle intent" on design-heavy feature work (their React/Redux example dropped 54→27). Fusion is not a universal win; there must be a solo fallback.

### Related evidence
- **Aider architect/editor**: R1 architect + Sonnet editor beat o1 solo at 14× lower cost. A weak planner hurts more than a weak executor (PEAR paper). Frontier-as-planner is the robust configuration.
- **Cognition "Multi-Agents: What's Actually Working"**: single-threaded writes + auxiliary intelligence work; reviewers should have **fresh context**.
- **Anthropic Advisor strategy** is Fusion inverted (cheap primary calls expensive advisor); it works but pays cache misses on every consult.

### Harness facts that shape the design
- **Claude Code** (v2.1.270): `claude -p --output-format stream-json` with `--allowedTools`, `--append-system-prompt`, `--mcp-config`, `--resume`, `--max-budget-usd`, `--json-schema`; `--output-format json` reports `total_cost_usd` and per-model usage. `fable` alias is on Max/Team Premium. **Do not use `--bare`** (it disables OAuth).
- **Anthropic terms**: OAuth is for "ordinary use of Claude Code and other native Anthropic applications"; third parties may not "offer Claude.ai login", "route requests through … plan credentials on behalf of their users", or "collect, store, or intermediate Claude.ai credentials or session tokens". Explicit carve-out: nothing "prevent[s] an end user from signing in to the unmodified Claude Code binary with their own Claude subscription". Subscription usage limits still apply to `claude -p`.
- **Codex CLI** (0.154.0): `codex exec --json` (JSONL events), `-m`, `--sandbox`, `-o last-message`, `--output-schema`, `codex exec resume <id>`; ChatGPT login works from a subprocess (verified here). Custom `[model_providers]` require the **Responses API**. `multi_agent` is stable. `codex app-server` is JSON-RPC if we ever need bidirectional control.
- **OpenCode**: model-agnostic (`opencode run --model provider/model --format json --session`), native OpenRouter support, MIT. The clean home for open-weight executors.
- **Cheap model routes into Claude Code**: Z.ai GLM Coding Plan, Moonshot Kimi and MiniMax officially document Anthropic-compatible endpoints; OpenRouter's Anthropic endpoint is only guaranteed for Anthropic models. Claude Code Router is the general proxy.
- **ACP** (Zed) would be a neat common abstraction but the Codex adapter is archived and the Claude adapter wraps the Agent SDK (which Anthropic says needs API keys). Drive native protocols instead.
- **Pricing (OpenRouter, Sept 2026)**: GLM-5.3 $1.40/$4.40, GLM-5.3-Flash $0.15/$0.50, DeepSeek V4 Flash $0.06/$0.12, MiniMax M3 $0.30/$1.20, Kimi K2.7-code $0.71/$3.50, Grok 4.6 $2/$6, GPT-5.6 Luna $0.20/$1.20, Haiku 4.5 $1/$5, Sonnet 5 $2/$10, Opus 5 $5/$25, Fable 5.1 $10/$50.

### Existing OSS and the gap
claw-orchestrator, awslabs cli-agent-orchestrator, oh-my-claudecode, ccswarm, claude-squad, vibe-kanban, Ralph loops, Aider architect. None combine (a) a persistent hands-off frontier lead, (b) a persistent tool-using cheap executor with its own cache, (c) escalation/switching, (d) cross-vendor fresh-context review, and (e) per-task cost accounting, all on **subscription auth**. That combination is the product.

---

## 3. Architecture

### 3.1 Options considered

| # | Option | How | Verdict |
|---|---|---|---|
| A | **Own harness** calling Anthropic/OpenAI APIs directly | Implement tool loop, editing, sandbox | ❌ Needs API keys (loses subscriptions), huge surface, re-invents what Claude Code/Codex do best |
| B | **External state machine** ("pipeline"): plan → execute → review as separate one-shot harness calls | Python loop, each step a fresh `claude -p` / `codex exec` | ✅ Simple, deterministic, harness-agnostic. ❌ Lead loses persistent context; re-reads plan each step; no dynamic delegation. Closest to claw-orchestrator |
| C | **Lead-in-harness with a role prompt + `delegate` tool** ("fusion") | Run the lead as one persistent `claude -p` / `codex exec` session, unchanged except for an appended role prompt and a `delegate` tool provided by `fusion`; the tool spawns and **resumes** persistent executor sessions | ✅ Faithful to Fusion: two persistent cached contexts, brief/result exchange, lead decides delegation dynamically, inherits harness tools/sandbox/caching. Minimal modification: two per-invocation flags. ❌ Relies on the lead following its role prompt (frontier models do; `--strict` exists if not) |
| D | **Native sub-agents with a different model** | `claude --agents '{"exec":{"model":"haiku"}}'` | ✅ Zero code. ❌ Same vendor only, no cross-vendor executor, lead unconstrained, no cost report. This is the user's current hack |

**Decision: C is the core ("fusion mode"); B is the outer loop for review and a `--mode pipeline` fallback.** D is what we're replacing.

### 3.2 The loop

```
 fusion "task"
   │
   ├─ 1. Lead session (persistent)   claude -p --model fable --append-system-prompt-file lead.md --mcp-config fusion-mcp.json
   │      (that's the whole modification: a role prompt + one extra tool; the harness keeps all its normal tools)
   │      lead.md: "You are the lead. Teammates: sidekick <exec spec> for implementation and tests,
   │                reviewer <review spec> for final review. Plan, brief, monitor, review. Delegate
   │                implementation; read only what you need to plan and verify."
   │
   │      tools exposed by fusion MCP server:
   │        delegate(brief, success_criteria, constraints, files_hint, effort) -> {result, diff_summary, cost, turns}
   │        sidekick_status() / sidekick_cancel()
   │        request_review(scope) -> {verdict, findings}        (Phase 2)
   │        escalate_to_me(reason)                              (lead takes over one subtask itself; Phase 2)
   │        done(summary)
   │
   ├─ 2. Sidekick session (persistent, resumed per brief)
   │      codex exec --json -m gpt-5.6-luna --sandbox workspace-write  [resume <thread-id>]
   │      or claude -p --model haiku --permission-mode acceptEdits --resume <id>
   │      or opencode run --model openrouter/z-ai/glm-5.3 --format json --session <id>
   │      system prompt: Fusion sidekick protocol (prescriptiveness tuned to model tier)
   │
   ├─ 3. Reviewer (fresh context, on lead's done())           (Phase 2)
   │      codex exec -m gpt-6-astra --sandbox read-only --output-schema review.json  (or claude:opus)
   │      verdict: approve | request_changes(findings) → fed back to lead as "reviewer feedback"; max N rounds
   │
   └─ 4. Report: wall-clock, per-role tokens/cost (claude total_cost_usd, codex usage, OpenRouter generation cost),
          turns, escalations, review rounds. Appended to .fusion/runs/<id>.json
```

Key mechanics:
- **Persistent sidekick context.** `delegate()` resumes the same executor session (`codex exec resume <id>`, `claude --resume <id>`, `opencode --session`). The sidekick accumulates repo understanding across briefs and its prompt cache stays warm — Fusion's central cost argument.
- **Lead is hands-off by instruction, not by surgery.** The role prompt tells the lead who its teammates are and that implementation goes to the sidekick; it keeps its full toolset. This matches Cognition's own description (the lead "should take minimal actions"), and frontier models follow role prompts reliably. The run report counts lead edits so drift is visible. An opt-in `--strict` flag removes Write/Edit from the lead (`--disallowedTools` on Claude, `--sandbox read-only` on Codex) for users who see the lead start typing code itself on long runs.
- **Zero-glue fallback.** If even the MCP server feels heavy, `delegate` can be a plain `fusion delegate "<brief>"` CLI the lead calls through Bash; the role prompt just names the command. Same persistence, less structure. Decide in Phase 1 after trying both.
- **Brief protocol.** Structured brief: objective, constraints, success criteria (tests to pass, commands to run), files hint, expected output shape, "ask back if ambiguous" allowed = yes/no (pushback knob). Sidekick returns: what changed, how verified, open questions, diff stat. Prescriptiveness ("tier") is a per-model config value: `tier = "small" | "mid" | "strong"`.
- **Escalation heuristics (Phase 2).** If a brief fails twice, exceeds turn/time budget, or the sidekick reports "unsure", the MCP server returns an `escalate` signal; the lead may re-brief more prescriptively, split the task, or call `escalate_to_me` which temporarily grants the lead edit tools for that subtask (implemented by spawning a scoped one-shot lead-model executor session). This is our cheap stand-in for Cognition's classifiers.
- **Single writer.** One sidekick edits at a time. Parallel sidekicks (worktrees) are Phase 3 and opt-in.
- **Budgets.** `--max-budget-usd` on Claude; turn/time caps on all roles; global `fusion --budget 2.00`.

### 3.3 Model/harness spec

`role = "<harness>:<model>[@<provider>]"`

| Spec | Meaning |
|---|---|
| `claude:fable` | Claude Code binary, user's Claude login, Fable alias |
| `claude:haiku` | same, Haiku |
| `codex:gpt-6-astra` | Codex binary, ChatGPT login |
| `codex:gpt-5.6-luna` | same, cheap model |
| `opencode:z-ai/glm-5.3@openrouter` | OpenCode binary, OpenRouter key from env/config |
| `opencode:x-ai/grok-4.6@openrouter` | same, Grok |
| `claude:glm-5.3@zai` | Claude Code binary pointed at Z.ai's Anthropic-compatible endpoint (their documented setup); metered on Z.ai plan, not Anthropic |
| `codex:glm-5.3@openrouter` | Codex binary with a custom `model_providers` entry; requires OpenRouter's Responses API (to verify in Phase 1) |

Providers are env-injected per spawned process only (`ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`, `OPENROUTER_API_KEY`, `-c model_provider=...`). We never modify a harness's global config or its stored credentials.

### 3.4 Presets

| Preset | Lead | Executor | Reviewer | For |
|---|---|---|---|---|
| `dual` (default when both logins found) | `claude:fable` | `codex:gpt-5.6-luna` | `codex:gpt-6-astra` | Claude Max + ChatGPT users; cross-vendor review |
| `claude` | `claude:fable` | `claude:haiku` | `claude:opus` | Claude-only sub |
| `codex` | `codex:gpt-6-astra` | `codex:gpt-5.6-luna` | `codex:gpt-6-astra` (fresh) | ChatGPT-only sub |
| `openrouter` | `claude:fable` | `opencode:z-ai/glm-5.3@openrouter` | `claude:opus` | Claude sub + OpenRouter key |
| `fast` | `claude:fable` | `opencode:x-ai/grok-build@openrouter` or Cerebras-hosted | `codex:gpt-6-astra` | speed-first |
| `byok` | `opencode:<frontier>@openrouter` | `opencode:<cheap>@openrouter` | `opencode:<frontier>@openrouter` | no subscriptions at all |

Presets are TOML files in `presets/`; users add their own in `~/.config/fusion/presets/`.

### 3.5 Legal/ToS posture (must hold for every phase)
- Spawn **unmodified** vendor binaries. Never patch, never re-implement their auth, never read `~/.claude` or `~/.codex` credential files, never set `--bare`, never proxy or share a login.
- Each user logs in with the vendor's own flow (`claude`, `codex login`). `fusion doctor` only checks *whether* a login exists by running the binary.
- Third-party endpoints are used only with the user's own key for that provider, injected into that child process's env.
- README states plainly: subscription usage counts against plan limits; Anthropic's terms say limits "assume ordinary, individual usage"; Anthropic reserves enforcement rights. Users choose.
- We don't use the Claude Agent SDK (Anthropic says SDK apps should use API keys); we use the CLI's public headless interface.

---

## 4. CLI UX

```bash
# install (one of)
uv tool install openfusion        # → `fusion` on PATH
uvx openfusion "fix the flaky test in tests/test_auth.py"   # zero-install

fusion init            # detects claude/codex/opencode binaries + logins, OPENROUTER_API_KEY, picks a preset, writes ~/.config/fusion/config.toml
fusion doctor          # same checks, plus a 1-token smoke run per role, prints what each role will cost per M tokens
fusion "add rate limiting to /api/upload with tests"        # run with default preset in cwd
fusion -p openrouter "…"                                    # choose preset
fusion --lead claude:fable --exec opencode:z-ai/glm-5.3@openrouter --review codex:gpt-6-astra "…"
fusion --mode pipeline "…"                                  # plan→exec→review one-shot mode (no persistent lead)
fusion --solo "…"                                           # lead does everything (control / fallback)
fusion --budget 3.00 --max-review-rounds 2 "…"
fusion presets | fusion models                              # list presets; list known models with $/M and tier
fusion runs | fusion runs show <id>                         # cost/time reports from .fusion/runs/
fusion resume <run-id> "also handle the edge case…"        # continue lead + sidekick sessions
```

Output: a compact live view (rich): lead thoughts collapsed, each `delegate()` as a card with brief title, sidekick progress lines, result, cost; final summary table by role. `--json` for scripting. `--verbose` streams raw events.

Config (`~/.config/fusion/config.toml`):
```toml
preset = "dual"

[presets.dual]
lead     = "claude:fable"
exec     = "codex:gpt-5.6-luna"
review   = "codex:gpt-6-astra"

[providers.openrouter]
api_key_env = "OPENROUTER_API_KEY"

[providers.zai]
base_url = "https://api.z.ai/api/anthropic"
api_key_env = "ZAI_API_KEY"

[budget]
max_usd = 5.00
max_exec_turns_per_brief = 40
max_review_rounds = 2
```

Project-level overrides in `.fusion/config.toml` (e.g. test command, "always run `uv run pytest` as success criterion").

---

## 5. Implementation plan

### Stack
- **Python 3.12, uv, hatchling.** Package `openfusion`, console script `fusion`. Rationale: author's stack; fastest path to a working tool; `mcp` Python SDK is mature for the stdio MCP server; asyncio subprocess handles three concurrent JSONL streams fine. Users already have Node for the harnesses, but we don't need it.
- Deps: `typer`, `rich`, `mcp`, `pydantic`, `tomli-w`. No database; run records are JSON files under `.fusion/runs/`.
- Tests: `pytest` with recorded JSONL fixtures from each harness (so CI runs without logins), plus an opt-in live smoke suite.

### Repo layout
```
openfusion/
  pyproject.toml
  src/openfusion/
    cli.py              # typer app: init, doctor, run (default), presets, models, runs, resume
    config.py           # TOML load/merge, role spec parsing
    roles.py            # Lead / Sidekick / Reviewer protocol prompts + tier-based prescriptiveness
    orchestrator.py     # run lifecycle, budgets, review loop, escalation, report
    mcp_server.py       # `fusion mcp` stdio server exposing delegate/status/done to the lead
    harness/
      base.py           # Harness ABC: start(prompt, model, tools, sandbox) / resume / stream events / cost
      claude.py         # claude -p stream-json adapter
      codex.py          # codex exec --json adapter (+ resume)
      opencode.py       # opencode run --format json adapter
    providers.py        # env injection for openrouter/zai/kimi/minimax/custom
    report.py           # cost + time accounting, run JSON, table rendering
  presets/*.toml
  prompts/lead.md prompts/sidekick.md prompts/reviewer.md
  docs/research/*.md
  tests/
```

### Phases

**Phase 0 — Research + plan (done, this doc).**

**Phase 1 — MVP "fusion mode" (target: 1 week of evenings)**
1. `Harness` adapters for `claude` and `codex` (start, resume, stream events, extract cost/usage, final message). Golden JSONL fixtures.
2. `fusion mcp` server: `delegate`, `sidekick_status`, `done`. Delegate = build brief → resume sidekick session → stream → return structured result.
3. `orchestrator.run()`: spawn lead with role prompt + `--mcp-config` pointing at `fusion mcp`; wait for `done`; write run report (including lead edit count).
4. `fusion init` / `fusion doctor` / default run / `presets` / `runs`. Presets `dual`, `claude`, `codex`.
5. Dogfood on 5 real tasks in this repo and in one of Andrew's big projects. Record cost + time vs `--solo`.
   **Exit criteria:** `fusion "…"` completes a multi-file change end-to-end on `dual`; report shows per-role cost; cheaper than solo Fable on ≥4/5 tasks with review-passing output.

**Phase 2 — Review, escalation, OpenRouter (1–2 weeks)**
1. `opencode` adapter + `openrouter`/`zai` providers; verify Codex `model_providers` against OpenRouter's Responses API (fallback: OpenCode for all BYOK executors).
2. Fresh-context reviewer with structured verdict (`--output-schema` / `--json-schema`), feedback loop, `max_review_rounds`.
3. Escalation: failure/turn/time triggers, re-brief guidance to lead, `escalate_to_me`.
4. Tier-aware sidekick prompts (small/mid/strong) and the pushback knob.
5. `fusion resume`, `--mode pipeline`, `--budget`, `--json`.
6. Publish `openfusion` to PyPI (private repo can still publish; or hold until Phase 3). Write README quickstart, ToS notice, CONTRIBUTING with "add a harness in one file".
   **Exit criteria:** 20-task internal eval (mix of bugfix, refactor, feature) on `dual` and `openrouter` presets vs solo; report table in `docs/evals/`. Decide go-public.

**Phase 3 — Public launch + breadth**
1. Make repo public; PyPI stable; Homebrew tap optional.
2. Codex-as-lead (Codex reads MCP servers from config; we pass `-c mcp_servers.fusion...`), OpenCode-as-lead for `byok`.
3. Parallel sidekicks in git worktrees (opt-in; lead decides independence; merge via rebase; single-writer remains default).
4. `gemini`, `cursor agent`, `droid` adapters via community.
5. Cost dashboard: `fusion runs` aggregate by week/preset.

**Phase 4 — Smarter switching**
- Cheap classifier (small model or heuristics on sidekick transcript) suggesting re-tier/escalate, applied at compaction boundaries like Cognition does.
- Optional "SWE-2-like" executor recommendations based on collected per-task cost data across users (opt-in telemetry, local-first).

---

## 6. Evaluation

- **Metrics per run:** wall-clock, per-role tokens and $ (Claude `total_cost_usd`; Codex usage × list price, or plan-usage proxy; OpenRouter generation cost), sidekick turns, escalations, review rounds, reviewer verdict, and human accept/reject.
- **Baselines:** `--solo` with the lead model (what Andrew does today without sub-agents), and native sub-agents (`claude --agents`, option D).
- **Task set:** 20 tasks from real repos, tagged {bugfix, refactor, feature, migration, test-writing}. Expect Fusion to win on bugfix/refactor/migration and be neutral-to-worse on design-heavy features (Cognition saw the same); the README should say so.
- **Subscription "cost"** is plan-quota burn, which we can't read directly. Proxy: list-price dollars per model (what `claude` already reports), and the qualitative "how often did I hit the 5-hour limit" note.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Anthropic tightens or enforces terms against orchestrated `claude -p` usage | Stay strictly in the "unmodified binary, own login" zone; document plainly; make every role BYOK-capable so users can switch the lead to `claude:opus@api-key` or `codex:` in one flag |
| Harness CLI churn breaks adapters | Pin tested versions in `fusion doctor`, golden-fixture tests per version, adapters are ~200 lines each |
| Codex custom providers require Responses API; OpenRouter support may be partial | Verify early in Phase 2; OpenCode is the guaranteed BYOK path |
| Quality loss on subtle/design tasks | Escalation, fresh reviewer, `--solo` one flag away, honest README |
| Lead over-reads or starts editing itself (kills the savings) | Role prompt + lead read/edit counters in the report; opt-in `--strict` tool removal; Phase 4 classifier |
| Running two/three agents in one repo concurrently corrupts state | Single writer; reviewer is read-only sandbox; lead has no write tools |
| Plan quota exhaustion mid-run | Detect rate-limit events in streams, pause + resume, offer `--fallback-exec` |

---

## 8. Open questions (decide during Phase 1)
1. Python vs TypeScript. Python chosen for velocity; revisit only if the MCP stdio server or JSONL streaming proves awkward.
2. Does prompt-only role discipline hold on long runs? Measure lead edit counts in Phase 1 dogfood; if it drifts, tighten the prompt first, make `--strict` the default only as a last resort.
3. Reviewer default: same vendor fresh session vs cross-vendor. Default cross-vendor when both logins exist (Andrew's current practice; diversity argument), else same vendor.
4. Where do sidekick sessions live between `fusion` invocations? Harness-native session IDs recorded in `.fusion/runs/<id>.json`; `fusion resume` reuses them.
5. Name collision: `fusion` command vs other tools named fusion. Keep `fusion`; also install `openfusion` alias.

---

## 9. Immediate next steps
1. Scaffold `pyproject.toml` + `src/openfusion` skeleton with `fusion doctor` detecting `claude`/`codex`/`opencode` and logins.
2. Claude and Codex adapters against recorded fixtures; live smoke test with `haiku` and `gpt-5.6-luna`.
3. `fusion mcp` with `delegate` + `done`; first end-to-end run on the `dual` preset against this repo ("write the README quickstart from PLAN.md").
4. Record first cost/time comparison vs `--solo`; post to AND-85.
