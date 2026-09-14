---
name: install-openfusion
description: Install and set up OpenFusion (the `fusion` CLI) on this machine. Use when the user asks to install, set up, configure, or troubleshoot OpenFusion / fusion, or wants Devin-Fusion-style lead + sidekick orchestration on their existing Claude / ChatGPT / OpenRouter accounts.
---

# Install OpenFusion

OpenFusion is a zero-dependency Python CLI (`fusion`) that runs the coding-agent CLIs the user already has logged in (`claude`, `codex`, `pi`, `grok`), assigns each a role, and orchestrates them. You are installing a tool, not building anything. Work through the steps in order, stop at the checkpoints, and report what you did.

Repo: https://github.com/andrewsiah/openfusion (MIT). Current version: 0.1.0.

## Ground rules

- **Never touch credentials.** Do not read, copy, or move `~/.claude`, `~/.codex`, OAuth tokens, or API keys. The user logs in to each harness themselves in their own terminal or browser. If a login is needed, tell the user the exact command to run and wait.
- **Ask before global installs.** Installing `fusion` itself is what the user asked for. Installing extra harnesses (`claude`, `codex`, `pi`) globally with npm is a separate decision: list what is missing and ask which ones they want.
- **Do not run login flows headlessly.** `claude`, `codex login`, and `grok` open a browser. They will hang or fail in a non-interactive shell.
- **Do not run `fusion smoke` without asking.** It spends real subscription usage and a few cents of OpenRouter credit, and takes about a minute.

## Step 1: Check prerequisites

Run:

```bash
python3 --version
```

Need Python 3.11 or newer. If `python3` is older, look for `python3.13`, `python3.12`, or `python3.11` on PATH. If none exist, stop and tell the user OpenFusion needs Python 3.11+ (suggest `uv python install 3.12` if `uv` is present, or their OS package manager).

Then detect which package managers exist:

```bash
command -v uv pipx npm brew pip 2>/dev/null
```

## Step 2: Install `fusion`

Pick the first available path in this order. Run exactly one.

| If available | Command |
|---|---|
| `uv` | `uv tool install git+https://github.com/andrewsiah/openfusion` |
| `pipx` | `pipx install git+https://github.com/andrewsiah/openfusion` |
| `npm` (Node 18+) | `npm install -g github:andrewsiah/openfusion` |
| `brew` (macOS/Linux) | `brew tap andrewsiah/tap && brew install andrewsiah/tap/openfusion` |
| none of the above | `git clone https://github.com/andrewsiah/openfusion && cd openfusion && pip install --user .` |

Notes:
- The npm path runs the bundled Python source with the first Python 3.11+ it finds (`python3.13`, `python3.12`, `python3.11`, `python3`, `python`). Override with `FUSION_PYTHON=/path/to/python`.
- PyPI and npm-registry names (`openfusion`) are reserved but not yet published; the git URLs above are the supported install path for v0.1.

**Checkpoint.** Verify:

```bash
fusion --version
```

Expected output: `fusion 0.1.0`. If `fusion` is not found, the tool bin directory is not on PATH. For `uv`, run `uv tool update-shell` and tell the user to open a new terminal. For `pipx`, run `pipx ensurepath`. Do not continue until this prints a version.

This also installs `fusion-delegate` and `fusion-cua`, the two tools the lead model calls. They must be on PATH for the same shell that runs `fusion`.

## Step 3: Inventory the harnesses

Each role needs a harness CLI. Check what exists:

```bash
command -v claude codex pi grok 2>/dev/null
```

Map to roles:

| Harness | Install | Login / key | Roles it can fill |
|---|---|---|---|
| `claude` (Claude Code) | `npm i -g @anthropic-ai/claude-code` | user runs `claude` once and signs in with their Claude plan | **lead** (v0.1: `claude:opus` or `claude:fable`), sidekick (`claude:haiku`), cua (`claude:sonnet`), reviewer |
| `codex` (Codex CLI) | `npm i -g @openai/codex` | user runs `codex login` with their ChatGPT plan | sidekick (`codex:gpt-5.6-luna`, the default), cua and reviewer (`codex:gpt-5.6-terra`, the default reviewer) |
| `pi` (Pi coding agent) | `npm i -g @mariozechner/pi-coding-agent` | `OPENROUTER_API_KEY` in the environment or in `./.env` | any BYOK model as sidekick/cua/reviewer, e.g. `pi:z-ai/glm-5.3@openrouter` |
| `grok` (Grok Build CLI) | xAI's installer | grok.com login | sidekick (`grok:grok-4.6`) |

Any role can be any harness. **In v0.1 the lead is spawned through Claude Code**, so `claude` is required for now (other lead harnesses are on the roadmap). Everything else depends on what the user pays for:

- Claude plan + ChatGPT plan: `claude` and `codex`. This is the built-in default and needs no config.
- Claude plan only: `claude` alone. Use `--exec claude:haiku --review claude:opus` (see Step 5).
- Claude plan + OpenRouter key: `claude` and `pi`. Use `--exec pi:z-ai/glm-5.3@openrouter`.

**Checkpoint.** Tell the user which harnesses are present and which are missing. Ask which missing ones to install. Install only what they approve. For any harness that needs a browser login, give the user the command and wait for them to confirm they are logged in before moving on.

## Step 4: Run the doctor

```bash
fusion doctor
```

It sends one tiny prompt through each installed harness and prints a PASS/FAIL/SKIP table with cost. SKIP means not installed or no key; that is fine for harnesses the user is not using. FAIL on a harness the user wants means a login or balance problem. Common fixes:

- `claude … no output`: user needs to run `claude` interactively once to sign in.
- `codex … run codex login`: user needs to run `codex login`.
- `pi … OPENROUTER_API_KEY not set`: export the key or write `OPENROUTER_API_KEY=sk-or-…` into `./.env` in the project directory. Never paste the key into chat.
- `pi … 402 … fewer max_tokens`: OpenRouter balance is below Pi's default 16k output cap. Set `FUSION_PI_MAX_TOKENS=4096` or have the user top up.
- `grok … 402 Payment Required`: Grok Build balance exhausted. Skip grok.

The exit code is 1 if anything FAILs. That is expected when an unused harness fails; judge by the rows the user actually needs.

## Step 5: Write defaults (optional)

If the user's setup differs from the built-in default (Claude lead + Codex sidekick + Codex reviewer), write `~/.config/fusion/config.toml`:

```toml
[defaults]
lead = "claude:opus"
exec = "codex:gpt-5.6-luna"
review = "codex:gpt-5.6-terra"
# cua = "codex:gpt-5.6-terra"          # optional computer-use agent for e2e tests
# test_cmd = "uv run pytest -q"        # per-project is usually better: pass --test-cmd instead
```

Valid values for each role are `harness:model[@provider]`, or `"none"` for `review` and `cua`. Common presets:

```toml
# Claude plan only
exec = "claude:haiku"
review = "claude:opus"

# Claude lead + OpenRouter sidekick
exec = "pi:z-ai/glm-5.3@openrouter"
review = "codex:gpt-5.6-terra"        # or "claude:opus" without a ChatGPT plan
```

Precedence is flags > `FUSION_*` env vars > config file > built-ins, so anything here can be overridden per run.

## Step 6: Prepare the project

In the repo the user will run `fusion` in:

1. Add `.fusion/` to `.gitignore` if it is not already there. Run reports and session state land in `.fusion/runs/` and `.fusion/state/`.
2. If the sidekick or cua will use Pi/OpenRouter, the key can live in `./.env` as `OPENROUTER_API_KEY=…` (fusion loads it, never overriding existing env). Make sure `.env` is gitignored.

## Step 7: Offer the end-to-end check

Ask the user whether to run the smoke test. It creates a throwaway repo with a failing test, runs the full lead → sidekick → reviewer loop, and reports PASS/FAIL per stage. It takes about 40 to 90 seconds and costs roughly $0.20 of Claude usage plus whatever the sidekick costs.

```bash
fusion smoke
```

Or with an explicit sidekick:

```bash
fusion smoke --exec pi:z-ai/glm-5.3@openrouter
```

All rows PASS means the install works. If `lead made no edits` fails, the lead ignored its role prompt; mention `--strict` for real runs. If `reviewer approved` fails but the tests are green, inspect the review verdict in the kept repo path the output prints.

## Step 8: Report

Tell the user, in a few lines:

- How `fusion` was installed and the version.
- Which harnesses passed `fusion doctor` and which roles they cover.
- Whether a config file was written and what defaults it sets.
- Whether the smoke test ran and its result.
- The one command to try next, from inside their repo:

```bash
fusion "describe the change you want" --test-cmd "your test command"
```

Changes land uncommitted in the working tree for the user to inspect. `fusion runs` lists past runs.

## Troubleshooting quick reference

| Symptom | Fix |
|---|---|
| `fusion: command not found` after install | tool bin dir not on PATH: `uv tool update-shell` / `pipx ensurepath`, open a new shell |
| npm postinstall fails: `needs python3 >= 3.11` | install Python 3.11+ or set `FUSION_PYTHON` |
| Codex sidekick: `bwrap: … Operation not permitted` | Codex's Linux sandbox is blocked on this host. Set `sandbox_mode` in `~/.codex/config.toml` or `export FUSION_CODEX_SANDBOX=workspace-write` |
| Lead does things from the user's global CLAUDE.md | keep the default safe mode (do not pass `--no-safe-mode`) |
| Lead edits files itself (`edits=` > 0 in report) | pass `--strict` |
| Reviewer hangs or errors | check `.fusion/state/<run>/review-last.json`; try `--review claude:opus` or `--review none` |
| Codex prints MCP auth errors at start | harmless noise from the user's Codex plugins |
