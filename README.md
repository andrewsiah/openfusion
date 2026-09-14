# OpenFusion

**Devin-Fusion-style orchestration on the AI subscriptions you already pay for.**

```bash
uv tool install git+https://github.com/andrewsiah/openfusion
fusion "add rate limiting to /api/upload with tests"
```

A frontier model you already pay for (Claude **Opus/Fable** on your Claude plan) is the **lead**: it plans, writes briefs, monitors, and verifies. A cheap, fast model is the **sidekick** that does the typing: **GPT-5.6 Luna** on your ChatGPT plan, **Haiku** on your Claude plan, or **GLM-5.3 / Grok / Kimi / DeepSeek** through your own OpenRouter key. A fresh-context **reviewer** (by default GPT-5.6 Terra on your ChatGPT plan) approves or requests changes before you see "done".

You get frontier judgment at a fraction of the frontier tokens and wall-clock, with no new API bill for the lead. Status: **v0.1, working prototype**. Private while we dogfood.

## Why

[Cognition's Devin Fusion](https://cognition.com/blog/devin-fusion) showed that a persistent frontier lead that only plans and reviews, paired with a persistent cheap sidekick that executes, cuts cost 23–46% at roughly equal quality. The insight: the smart model should be the *planner*, not the *typist*, and the two should exchange **briefs and results**, not whole conversations.

OpenFusion doesn't build a new agent harness. It runs the **unmodified** coding-agent CLIs you already have logged in (`claude`, `codex`, `pi`, `grok`), assigns each a role, and gives the lead one extra tool: `fusion-delegate "<brief>"`. That's the whole trick. Research notes: [docs/research/](docs/research/). Plan: [PLAN.md](PLAN.md).

## Install

Pick whichever package manager you already use. All paths need only **Python ≥ 3.11** on your machine (the package itself has zero dependencies).

```bash
# uv (recommended)               → `fusion`, `fusion-delegate`, `fusion-cua` on PATH
uv tool install git+https://github.com/andrewsiah/openfusion

# npm  (you already have node for claude/codex; runs the bundled Python source with your python3)
npm install -g github:andrewsiah/openfusion

# Homebrew (tap; --HEAD while the repo is private)
brew tap andrewsiah/tap && brew install --HEAD andrewsiah/tap/openfusion

# pipx / pip
pipx install git+https://github.com/andrewsiah/openfusion

# from source
git clone https://github.com/andrewsiah/openfusion && cd openfusion && uv tool install .
```

`fusion --version` should print `fusion 0.1.0`. Once the repo is public, `uv tool install openfusion`, `npm i -g openfusion`, and a stable `brew install andrewsiah/tap/openfusion` will work without the git URL. The npm wrapper picks the first Python ≥ 3.11 it finds (`python3.13`, `python3.12`, `python3.11`, `python3`, `python`); override with `FUSION_PYTHON=/path/to/python`.

Then install and log in to the harnesses for the roles you want. You need at least the lead's:

| Harness | Install | Log in / key | Used for |
|---|---|---|---|
| Claude Code | `npm i -g @anthropic-ai/claude-code` | run `claude` once and sign in with your Claude plan | lead (`claude:opus`, `claude:fable`), sidekick (`claude:haiku`), cua (`claude:sonnet` + `--chrome`), reviewer |
| Codex CLI | `npm i -g @openai/codex` | `codex login` with your ChatGPT plan | sidekick (`codex:gpt-5.6-luna`), cua and reviewer (`codex:gpt-5.6-terra`) |
| Pi | `npm i -g @mariozechner/pi-coding-agent` | `export OPENROUTER_API_KEY=sk-or-…` (or put it in `./.env`) | any BYOK model: `pi:z-ai/glm-5.3@openrouter`, `pi:x-ai/grok-4.6@openrouter`, `pi:grok-4.6@xai` … |
| Grok Build CLI | xAI's `grok` | grok.com login | sidekick (`grok:grok-4.6`) |

Check everything in one go:

```bash
fusion doctor
```

```
check                          status time    detail
claude:haiku                   PASS   7.6s    result='OK' cost=$0.0269
codex:gpt-5.6-luna             PASS   7.0s    result='OK' in=22266 cached=9984
grok:grok-4.6                  FAIL   1.0s    402 Payment Required: Grok Build usage balance exhausted
pi:z-ai/glm-5.3@openrouter     PASS   1.8s    result='OK' cost=$0.0003
```

## First run

Prove the loop works on a throwaway repo (seeds a failing test; the lead must fix it *through* the sidekick and the reviewer must approve):

```bash
fusion smoke                                   # defaults: lead claude:opus, sidekick codex:gpt-5.6-luna, reviewer codex:gpt-5.6-terra
fusion smoke --exec pi:z-ai/glm-5.3@openrouter # GLM as the sidekick
```

Then run a real task from inside your repo:

```bash
cd your-project
fusion "Make slugify() handle unicode and collapse repeated hyphens; add unittest cases" --test-cmd "python3 -m unittest -q"
```

What you see:

```
fusion run 20260914-190040-3c3241  lead=claude:opus  sidekick=pi:z-ai/glm-5.3@openrouter  reviewer=codex:gpt-5.6-terra
lead: Verified: diff is confined to ... DONE: Fixed add() in calc.py ...
review: approve — calc.py correctly changes add() to return a + b ...
status: done   wall: 39.0s
role       spec                                  time  detail
lead       claude:opus                          19.5s  turns=6 delegations=1 edits=0 cost=$0.1975
sidekick   pi:z-ai/glm-5.3@openrouter            3.5s  briefs=1 cost=$0.0032
review 1   codex:gpt-5.6-terra                  19.5s  approve: ...
```

The lead never edits files itself (`edits=0`); it briefs the sidekick, verifies with your test command and `git diff`, and reports `DONE:`. The reviewer then checks the diff with fresh context. If it requests changes, the feedback goes back to the lead's live session for one more round. Changes land **uncommitted** in your working tree for you to inspect and commit. Reports are saved to `.fusion/runs/`; `fusion runs` lists them. Add `.fusion/` to your `.gitignore`.

## The CUA role (computer-use agent)

Coding models and computer-use models sit on different cost/capability curves, so the **CUA** (computer-use agent) is its own role with its own spec. It runs the end-to-end tests, and any other computer-use task the lead needs: reproduce a bug in the browser, exercise a workflow, check a live page. When set, the lead gets a second tool, `fusion-cua "<brief>"`, and is told to e2e-test through it before reporting DONE: run the CLI or app as a user would, hit endpoints, click through the UI if the harness has browser/computer-use tools, and report PASS/FAIL per scenario with evidence. The CUA never edits source; the lead turns its FAIL findings into new sidekick briefs.

```bash
fusion "add a --json flag to the CLI" --cua codex:gpt-5.6-terra --test-cmd "python3 -m unittest -q"
fusion "fix the signup form validation" --cua claude:sonnet   # with FUSION_CUA_ARGS="--chrome" for Claude in Chrome
```

Pick a harness with the tools your app needs: Codex has browser/computer-use built in; Claude Code can drive Chrome (`FUSION_CUA_ARGS="--chrome"`) or a Playwright MCP server; Pi/OpenRouter models suit CLI and HTTP flows. `FUSION_EXEC_ARGS` does the same for the sidekick. The CUA keeps its own persistent session like the sidekick, and shows up as its own row in the report. Config key: `cua = "codex:gpt-5.6-terra"`; env `FUSION_CUA`.

## Choosing models

Every role is `harness:model[@provider]`:

```bash
fusion "…" --lead claude:opus  --exec codex:gpt-5.6-luna          --review codex:gpt-5.6-terra   # Claude + ChatGPT plans (default)
fusion "…" --lead claude:opus  --exec claude:haiku                --review claude:opus           # Claude plan only
fusion "…" --lead claude:fable --exec pi:z-ai/glm-5.3@openrouter  --review codex:gpt-5.6-terra   # OpenRouter sidekick
fusion "…" --lead claude:opus  --exec pi:x-ai/grok-4.6@openrouter --review none                   # no reviewer
fusion "…" --solo                                                                                 # baseline: Opus does everything itself
```

Set your own defaults once in `~/.config/fusion/config.toml`:

```toml
[defaults]
lead = "claude:opus"
exec = "pi:z-ai/glm-5.3@openrouter"
review = "codex:gpt-5.6-terra"
test_cmd = "uv run pytest -q"
```

Or with env vars `FUSION_LEAD`, `FUSION_EXEC`, `FUSION_REVIEW`, `FUSION_TEST_CMD`. Precedence: flags > env > config > built-ins.

Useful flags: `--test-cmd` (the lead may run it to verify; it's also handed to the reviewer), `--allow 'Bash(npm test*)'` (extra lead tool rule), `--budget 2.00` (cap the lead's spend), `--max-review-rounds 2`, `--strict` (also *remove* Edit/Write from the lead instead of relying on the prompt), `--no-safe-mode` (let the lead load your CLAUDE.md, hooks and skills; off by default so personal automation doesn't leak into the role).

## How it works

```
fusion "task"
  ├─ Lead      claude:opus            one persistent Claude Code session, plus a role prompt and the
  │                                   fusion-delegate tool. Plans, briefs, verifies, reports DONE.
  ├─ Sidekick  codex / pi / claude    one persistent session, resumed per brief (its prompt cache stays warm).
  │                                   Edits files, runs tests, reports back.
  ├─ CUA       codex / claude / pi    optional computer-use agent; e2e tests + other computer-use tasks via fusion-cua, own session, never edits.
  ├─ Reviewer  codex / claude         fresh context, read-only, strict-JSON verdict; 1 feedback round by default.
  └─ Report    .fusion/runs/<id>.json wall-clock, per-role turns/tokens/cost, lead edit count.
```

Design choices, all from Cognition's write-ups and our first runs: the lead is hands-off *by instruction*, not by tool surgery (frontier models follow the role prompt; `--strict` exists if yours doesn't); one sidekick writes at a time; reviewers get fresh context; measure cost per task, not per token. Full rationale in [PLAN.md](PLAN.md).

## Subscription usage and terms

OpenFusion never reads, stores, or proxies your Claude or ChatGPT credentials. It runs the vendors' own unmodified CLIs, which you log into yourself, and injects only your BYOK provider keys into the child process that needs them. Subscription usage still counts against your plan limits. Anthropic's terms say plan limits "assume ordinary, individual usage of Claude Code" and reserve enforcement rights; if that concerns you, point the lead at an API key or another vendor with one flag. Details in [docs/research/harnesses.md](docs/research/harnesses.md).

## Troubleshooting

- **`402 … fewer max_tokens` from OpenRouter (Pi)**: your balance can't cover Pi's default 16k output cap. Top up, or `export FUSION_PI_MAX_TOKENS=4096`; fusion-delegate then writes a private Pi model config with that cap and the model's OpenRouter price.
- **Codex sidekick fails with `bwrap: … Operation not permitted`**: Codex's Linux sandbox doesn't work on that VM. fusion inherits your `~/.codex/config.toml` `sandbox_mode`; set it there, or `export FUSION_CODEX_SANDBOX=workspace-write` where bwrap works.
- **`fusion-cua` says "no CUA configured"**: pass `--cua <spec>` (or set `cua` in config); without it the lead is told to verify via the sidekick and test command.
- **Lead ignores the role / does things from your global instructions**: keep the default safe mode. Codex sidekicks still read `~/.codex/AGENTS.md`; the sidekick prompt tells them the lead owns task tracking, so tracker-heavy global instructions don't fire.
- **Lead edits files itself**: check `edits=` in the report; add `--strict`.
- **Reviewer says `error` or hangs**: see `.fusion/state/<run>/review-last.json` and `lead.jsonl`; try `--review claude:opus` or `--review none`.
- **Codex prints MCP auth errors at start**: harmless noise from your Codex plugins' MCP servers.

## Contributing

Adding a harness is one function in `src/openfusion/delegate.py` (spawn it, resume it, parse its final message and usage). Adding a reviewer harness is one branch in `core.run_review`. Please run `fusion smoke` before opening a PR. MIT licensed.
