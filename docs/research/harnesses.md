# Driving existing coding-agent harnesses on the user's own subscriptions (as of 2026-09-14)

Verified locally on newyorkailabs-vm: Claude Code v2.1.270 (claude.ai login), Codex CLI 0.154.0 (ChatGPT login). Both were exercised as subprocesses.

## 1. Claude Code as a programmable harness

**Headless surface.** `claude -p "<prompt>"` runs non-interactively. Relevant flags: `--output-format text|json|stream-json`, `--input-format stream-json` (realtime streaming input), `--include-partial-messages`, `--forward-subagent-text`, `--json-schema`, `--max-budget-usd`, `--permission-prompts host|none`, `--session-id`, `--resume <id>`, `--continue`, `--fork-session`, `--mcp-config <json|file>`, `--strict-mcp-config`, `--allowedTools/--disallowedTools` (`Bash(git diff *)` syntax), `--permission-mode acceptEdits|auto|bypassPermissions|manual|dontAsk|plan`, `--append-system-prompt[-file]`, `--system-prompt`, `--agents <json>`, `--effort low..max`, `--fallback-model`, `--restricted`. `--output-format json` returns `session_id`, `total_cost_usd`, per-model `modelUsage`, `permission_denials`, `subagent_stats` (confirmed by a live `--model haiku` run, $0.019). Docs: https://code.claude.com/docs/en/headless

**`--bare` caveat.** `--bare` never reads OAuth credentials and requires `ANTHROPIC_API_KEY`. A subscription-funded subprocess must **not** use `--bare`.

**Models.** `--model` aliases: `default`, `best`, `fable`, `opus`, `sonnet`, `haiku`, `opusplan`, `[1m]` variants, or full IDs. `fable` is available on Max, Team Premium, Enterprise, API (not Pro). Env remaps: `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU,FABLE}_MODEL`, `ANTHROPIC_DEFAULT_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL`. https://code.claude.com/docs/en/model-config

**Subagents.** `--agents '{"name":{"description","prompt","tools","model","permissionMode","maxTurns","effort","background","isolation"}}'`; `model` accepts `sonnet|opus|haiku|fable|<id>|inherit`. Nest up to 3 levels. https://code.claude.com/docs/en/sub-agents

**Auth and terms — the key constraint.** From https://code.claude.com/docs/en/legal-and-compliance:

> "OAuth authentication is intended exclusively for purchasers of Claude Free, Pro, Max, Team, and Enterprise subscription plans and is designed to support ordinary use of Claude Code and other native Anthropic applications."
> "Developers building products or services that interact with Claude's capabilities, including those using the Agent SDK, should use API key authentication… Anthropic does not permit third-party developers to offer Claude.ai login into their own applications, or to route requests through Free, Pro, or Max plan credentials on behalf of their users. Moreover, developers may not collect, store, or intermediate Claude.ai credentials or session tokens."
> "Nor does it prevent an end user from signing in to the unmodified Claude Code binary with their own Claude subscription…"
> Embedding conditions: "The Claude Code binary must not be modified… customers may not remove, disable, or restrict any authentication method built into it" and "Each end user must authenticate with their own Anthropic API key, Claude subscription plan credentials, or 3P inference provider credential."

Reading: an open-source orchestrator that spawns the **unmodified `claude` binary**, where the user logged in themselves via Claude's own flow, is in the explicitly carved-out zone. Anything that touches OAuth tokens, spoofs the harness, or "offers Claude login" is prohibited. Enforcement history: OpenCode's consumer-OAuth use blocked 2026-01-09; ban written into terms Feb 2026; from 2026-04-04 subscriptions stopped covering third-party harness traffic. A June 2026 support article about a monthly "Agent SDK credit" now says the change is paused: "Claude Agent SDK, `claude -p`, and third-party app usage still draw from your subscription's usage limits." Also: "Advertised usage limits for Pro and Max plans assume ordinary, individual usage of Claude Code and the Agent SDK." (https://support.claude.com/en/articles/15036540)

## 2. Routing Claude Code to other models

- `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` (or `ANTHROPIC_API_KEY`). When a credential var is set, the claude.ai subscription isn't used. Anthropic "doesn't support routing Claude Code to non-Claude models through any gateway" (unsupported, not prohibited). https://code.claude.com/docs/en/llm-gateway
- **OpenRouter** exposes an Anthropic Messages endpoint at `ANTHROPIC_BASE_URL=https://openrouter.ai/api`, but states it is "only guaranteed to work with the Anthropic first-party provider". https://openrouter.ai/blog/tutorials/claude-code-openrouter/
- **Z.ai GLM Coding Plan** (officially documented for Claude Code): `ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`, `ANTHROPIC_AUTH_TOKEN=<zai key>`, `ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-5.3-flash`, `ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5.3`, `ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5.3`. Plan "from 18 USD/month". https://docs.z.ai/devpack/tool/claude
- **Moonshot Kimi** (official): `ANTHROPIC_BASE_URL=https://api.moonshot.ai/anthropic`, model `kimi-k2.7-code`. **MiniMax** (official): `https://api.minimax.io/anthropic` for M2.7/M3.
- **xAI**: Anthropic-compat status conflicting/unverified (x.ai returned 403).
- **Claude Code Router** (musistudio, ~33k stars): local proxy exposing one Anthropic-format endpoint, routing to OpenRouter/DeepSeek/Moonshot/Z.AI/custom. https://github.com/musistudio/claude-code-router

## 3. OpenAI Codex CLI as a harness

Verified (`codex exec --help`, 0.154.0): `codex exec [PROMPT]`, `--json` (JSONL: `thread.started`, `turn.started/completed/failed`, `item.*`, `error`), `-o/--output-last-message`, `--output-schema <file>`, `-m/--model`, `-c key=value`, `-s/--sandbox read-only|workspace-write|danger-full-access`, `-a/--ask-for-approval on-request|never`, `--approve-for-me`, `--ephemeral`, `--skip-git-repo-check`, `--worktree`, `codex exec resume <id>|--last`, `codex exec fork`. `--full-auto` deprecated in favor of explicit `--sandbox`. https://learn.chatgpt.com/docs/non-interactive-mode

**Subscription login from a subprocess works.** `codex exec --json -m gpt-5.6-luna "Reply OK"` ran here on the ChatGPT login. No OpenAI statement found prohibiting driving the official Codex binary/SDK on a ChatGPT plan (nor an explicit blessing for non-Codex clients using the OAuth token). https://learn.chatgpt.com/docs/auth

**Custom providers.** `[model_providers.<id>]` with `name`, `base_url`, `env_key`, `wire_api` (docs say only `responses` is supported now), `http_headers`, etc.; select via `model_provider` + `model`. Implication: OpenAI-compatible providers must speak the **Responses API**, not just Chat Completions. `--oss` / `--local-provider lmstudio|ollama` for local models. https://learn.chatgpt.com/docs/config-file/config-reference

**Subagents.** `multi_agent` feature stable; agents as TOML in `~/.codex/agents/` or `.codex/agents/` with `name`, `description`, `developer_instructions`, `model`, `model_reasoning_effort`, `sandbox_mode`, `mcp_servers`; `default_subagent_model`. https://learn.chatgpt.com/docs/agent-configuration/subagents

**SDK / app-server.** `@openai/codex-sdk` (TS), `openai-codex` (Python) drive the local app-server over JSON-RPC; `codex app-server` speaks JSON-RPC 2.0 over stdio or `--listen ws://…` (`initialize`, `thread/start`, `turn/start`, approval callbacks). Third-party reports say the SDK inherits `codex login` credentials. https://learn.chatgpt.com/docs/app-server

## 4. Other harnesses

| Harness | Headless | Auth / billing |
|---|---|---|
| **OpenCode** (SST) | `opencode run --model --format json --agent --session`; `opencode serve`; `opencode acp` | 75+ providers via Models.dev incl. OpenRouter; ChatGPT login via community plugin; Claude subscription login not sanctioned since early 2026 |
| **Gemini CLI** | `gemini -p … --output-format json|stream-json` | Google account free quota or API key (unverified here) |
| **Cursor CLI** | `agent -p --output-format stream-json --force` | `CURSOR_API_KEY` / Cursor subscription |
| **Aider** | `--message`, Python `Coder` API | BYO API keys |
| **Factory Droid** | `droid exec` json / stream-jsonrpc, `--auto` | Factory key |
| **Pi** | BYOK, MIT, minimal | provider keys |

## 5. ACP as a common abstraction

ACP (Zed) is JSON-RPC over stdio, reuses MCP types, adds diffs/permissions. Adapters: `@zed-industries/claude-code-acp` (wraps the Agent SDK, so inherits the Anthropic third-party restriction), `zed-industries/codex-acp` (**archived 2026-07-22**; community forks), Gemini CLI, OpenCode (`opencode acp`). Assessment: good client-side normalization but adapters lag vendors and the two most important adapters are fragile for a subscription-preserving orchestrator. Pragmatic alternative: drive each vendor's own protocol (`claude -p --input-format stream-json --output-format stream-json`, `codex exec --json` / `codex app-server`) and normalize in our CLI.

## 6. Cheap/fast models and pricing (Sept 2026)

OpenRouter live prices 2026-09-14 unless noted. Tokens/sec mostly unverified.

| Model | $/M in | $/M out | Ctx | SWE-bench Verified* |
|---|---|---|---|---|
| GLM-5.3 (Z.ai) | 1.40 | 4.40 | 1.3M | GLM-5: 77.8 |
| GLM-5.3-Flash | 0.15 | 0.50 | 1.3M | — |
| Kimi K2.7-code | 0.71 | 3.50 | 262k | K2.6: 80.2 |
| DeepSeek V4 Pro | 0.66 | 1.98 | 1M | 80.6 |
| DeepSeek V4 Flash | 0.06 | 0.12 | 1.3M | 79.0 |
| Qwen3.7 Plus | 0.32 | 1.28 | 1M | 77.7 |
| Qwen3 Coder Next | 0.12 | 0.80 | 262k | ~71 |
| MiniMax M2.7 / M3 | 0.30 | 1.20 | 205k / 1M | M3: 80.5 |
| Grok 4.6 (xAI) | 2.00 | 6.00 | 500k | Grok 4.20: 76.7 |
| Grok Build 0.1 | 1.00 | 2.00 | 256k | — |
| Claude Haiku 4.5 | 1.00 | 5.00 | 200k | 73.3 |
| Claude Sonnet 5 | 2.00 | 10.00 | 1M | 85.2 |
| Claude Opus 5 | 5.00 | 25.00 | 1M | 96 |
| Claude Fable 5.1 | 10.00 | 50.00 | 1M | Fable 5: 95 |
| GPT-5.6 Luna / Terra / Sol | 0.20 / 2.00 / 2–4 | 1.20 / 12.00 / 10–20 | 1M | — |
| GPT-5.5 | 5.00 | 30.00 | 1M | — |

*BenchLM leaderboard 2026-09-10; benchmark is saturated at the top. Fast hosts: Cerebras gpt-oss-120b ~3,000 tok/s, Groq ~500 tok/s (third-party). Cognition's SWE-2 sidekick is $0.75/Mtok (Kimi K3 post-train). Subscriptions: Z.ai GLM Coding Plan from $18/mo; MiniMax Token Plan ~$22+/mo; Claude Pro/Max and ChatGPT plans include their CLIs.

## Bottom line for a third-party orchestrator CLI

1. **Codex**: spawn `codex exec --json` or `codex app-server`; ChatGPT login works from a subprocess today (verified), no prohibition found.
2. **Claude Code**: spawn the unmodified `claude -p` binary with the user's own login; never touch tokens; never add `--bare`. This is the only subscription path Anthropic's text leaves open, and usage counts against plan limits.
3. **Cheap models**: Claude Code → Z.ai/Kimi/MiniMax Anthropic-compatible endpoints or Claude Code Router; Codex → any Responses-API provider via `model_providers`; OpenCode → anything via OpenRouter natively.
4. **ACP** is useful but adapter-dependent; native stream-json/JSON-RPC is more robust.

## Sources
- https://code.claude.com/docs/en/headless · /model-config · /sub-agents · /legal-and-compliance · /agent-sdk/overview · /llm-gateway
- https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan
- https://alternativeto.net/news/2026/2/anthropic-officially-bans-using-subscription-authentication-for-third-party-claude-use
- https://openrouter.ai/blog/tutorials/claude-code-openrouter/ · https://docs.z.ai/devpack/tool/claude · https://platform.kimi.ai/docs/guide/agent-support · https://platform.minimax.io/docs/token-plan/claude-code · https://github.com/musistudio/claude-code-router
- https://learn.chatgpt.com/docs/non-interactive-mode · /config-file/config-reference · /codex-sdk · /agent-configuration/subagents · /auth · /app-server
- https://opencode.ai/docs/cli/ · https://geminicli.com/docs/cli/headless/ · https://cursor.com/docs/cli/headless · https://docs.factory.ai/cli/droid-exec/overview
- https://agentclientprotocol.com/overview/introduction · https://github.com/zed-industries/codex-acp
- https://platform.claude.com/docs/en/about-claude/pricing · https://developers.openai.com/api/docs/pricing · https://benchlm.ai/benchmarks/swe-bench-verified

Could not verify: Anthropic consumer-terms text itself; OpenAI help-center and x.ai API pages (403); Cerebras lineup; most tokens/sec; Z.ai Pro/Max prices.
