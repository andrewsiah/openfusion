---
name: use-fusion
description: Run a big or repetitive coding task through OpenFusion (`fusion`) instead of doing it yourself. Use when the user says "use fusion", "fusion this", "orchestrate this", "run this with a lead and sidekick", "you orchestrate, subagents execute", names roles like lead / sidekick / orchestrator / subagent / tester / reviewer, or names models per role (e.g. "Claude as lead, Terra as sidekick, Terra as e2e tester").
---

# Use Fusion

You are a coding agent the user is already talking to. When they say **"use fusion"**, they want you to hand the task to OpenFusion, which runs a frontier **lead** that plans and verifies, a cheap **sidekick** that types, an optional **CUA** (computer-use agent) that runs end-to-end tests, and a fresh-context **reviewer**. It is faster and cheaper than you doing the whole thing in one context, and the user knows that. Your job is to build the right `fusion` command from what they said and what you know about the repo, run it, and relay the result.

Do not implement the task yourself. Do not "help" by editing files while `fusion` is running.

## Step 1: Make sure fusion is installed

```bash
fusion --version
```

Expected `fusion 0.1.0` or newer. If it is missing, stop and offer to install it by following `skills/install-openfusion/SKILL.md` in the OpenFusion repo (https://github.com/andrewsiah/openfusion). Do not proceed until it is installed.

## Step 2: Translate what the user said into roles

Every role is `harness:model[@provider]`. Users speak loosely. Map their words:

**Role synonyms**

| User says | Fusion role | Flag |
|---|---|---|
| lead, orchestrator, planner, architect, manager, "you" (the frontier model) | lead | `--lead` |
| sidekick, subagent, sub-agent, worker, executor, implementer, coder, typist | sidekick | `--exec` |
| tester, e2e tester, QA, end-to-end, "test it in the browser", computer-use | cua | `--cua` |
| reviewer, critic, second opinion, "have X check it" | reviewer | `--review` |

**Model nicknames**

| User says | Spec | Needs |
|---|---|---|
| Claude, Opus, "Claude Code" | `claude:opus` | Claude plan, `claude` logged in |
| Fable | `claude:fable` | Claude Max / Team Premium |
| Sonnet | `claude:sonnet` | Claude plan |
| Haiku | `claude:haiku` | Claude plan |
| Terra, "Codex Terra", GPT Terra | `codex:gpt-5.6-terra` | ChatGPT plan, `codex login` |
| Luna, "Codex Luna" | `codex:gpt-5.6-luna` | ChatGPT plan |
| Codex (no model named) | `codex:gpt-5.6-luna` for sidekick, `codex:gpt-5.6-terra` for cua/reviewer | ChatGPT plan |
| GLM | `pi:z-ai/glm-5.3@openrouter` | `pi` + `OPENROUTER_API_KEY` |
| Grok | `grok:grok-4.6` (Grok Build CLI) or `pi:x-ai/grok-4.6@openrouter` | grok login, or `pi` + OpenRouter |
| any other OpenRouter model | `pi:<openrouter-slug>@openrouter`, slug exactly as shown on openrouter.ai | `pi` + `OPENROUTER_API_KEY` |
| "no reviewer", "skip review" | `--review none` | |

**Defaults when the user does not say.** Lead `claude:opus`, sidekick `codex:gpt-5.6-luna`, reviewer `codex:gpt-5.6-terra`, no cua. The user may have their own defaults in `~/.config/fusion/config.toml`; flags override them, so only pass flags for roles the user actually named.

**Lead limitation in v0.1.** The lead is spawned through Claude Code, so `--lead` must be `claude:*` today. If the user asks for a Codex, Pi, or Grok lead, say so in one sentence, propose `claude:opus` (or `claude:fable`) as lead with their model in another role, and continue unless they object.

**Example.** "Use fusion, Claude as lead, Terra as sidekick, Terra as the e2e tester":

```bash
fusion "<task>" --lead claude:opus --exec codex:gpt-5.6-terra --cua codex:gpt-5.6-terra --test-cmd "<tests>"
```

## Step 3: Write the task string

This is where you add the most value. The Fusion lead starts with a fresh context in safe mode: it does not see your conversation, your `CLAUDE.md` or `AGENTS.md`, or anything you have learned about the repo. Put that into the task string. Quote it as one shell argument.

Include, in plain sentences:

- **The outcome** the user wants, in their words, plus anything they clarified earlier in the conversation.
- **Where in the repo** it lives: the files, modules, or directories you already know are involved.
- **Constraints**: what not to touch, conventions to follow, public APIs to keep, style the user cares about.
- **Done means**: which tests must pass, which behavior must be observable, what the diff should and should not contain.

Keep it under about 30 lines. Do not paste file contents; the sidekick will read them. Do not include secrets.

**Always pass `--test-cmd`** with the project's real test or build command (`uv run pytest -q`, `npm test`, `go test ./...`, `python3 -m unittest -q`). The lead may run it to verify, and the reviewer gets it too. If the test command is not obvious, look at `package.json`, `pyproject.toml`, `Makefile`, or CI config before you run fusion.

Useful extras:

| Flag | When |
|---|---|
| `--budget 2.00` | user mentions a spend cap in USD (lead only) |
| `--max-review-rounds 2` | user wants more back-and-forth with the reviewer |
| `--allow 'Bash(npm run lint*)'` | the lead needs to run one more command beyond the test command |
| `--strict` | a previous run showed `edits=` > 0 for the lead |
| `-C path/to/repo` | the task is in a different directory than your cwd |

## Step 4: Run it

Run from the repo root (or pass `-C`). A run takes anywhere from one to thirty minutes depending on the task, so:

- Use a long timeout (at least 30 minutes) or run it in the background and poll `.fusion/runs/` for the new `<id>.json`.
- Do not edit files in the repo while it runs. Two writers make a mess.
- Progress streams to stdout: `lead: …` lines, `review: …` lines, then a summary table.

Exit code 0 means the lead reported `DONE:` and the reviewer approved (or there was no reviewer). Exit code 1 means `BLOCKED:`, reviewer requested changes past the round limit, or a harness failed.

**If you are running inside a sandbox** (Codex CLI's default `workspace-write`, or a restricted Claude Code permission mode), `fusion` needs to spawn `claude`, `codex`, or `pi` as child processes with network access. If the run fails immediately with a permission or network error, tell the user to run the exact command in their own terminal instead of through you, and give them the command.

## Step 5: Relay the result

Read the summary table at the end of the output (or the newest `.fusion/runs/<id>.json`). Then check what actually changed:

```bash
git status --short && git diff --stat
```

Report to the user in a few lines:

- Status (`done`, `blocked`, or `changes_requested`) and the lead's one-line `DONE:` / `BLOCKED:` summary.
- What changed: files touched, from `git diff --stat`.
- Reviewer verdict and its main finding, if there was a reviewer.
- Wall-clock and cost per role from the table. Note `edits=` on the lead row: it should be 0.
- CUA PASS/FAIL scenarios, if a cua was set.

Changes are left **uncommitted** in the working tree. Do not commit unless the user asks. Offer to run the tests yourself, show the diff, or commit.

If the status is `blocked`, quote the blocker and ask the user how to proceed. Common blockers: a harness not logged in (`fusion doctor` shows which), a test command that does not exist, or a task too ambiguous for the lead. Do not silently finish the task yourself; the user chose Fusion for a reason.

## Step 6: Follow-ups

Each `fusion` call is a new run with a fresh lead and sidekick. For "now also do X" or "the reviewer was right, fix Y", run `fusion` again with a task string that says what the previous run did and what to change now. For a review of the current uncommitted diff without another implementation pass:

```bash
fusion review "<what the change was supposed to do>" --test-cmd "<tests>"
```

`fusion runs` lists past runs with status, wall time, and lead cost. Suggest adding `.fusion/` to `.gitignore` if it is not there.

## Quick reference

```bash
fusion "<task>" [--lead SPEC] [--exec SPEC] [--review SPEC|none] [--cua SPEC] --test-cmd "<cmd>" [--budget USD] [--strict] [-C DIR]
fusion review "<task>" --test-cmd "<cmd>"     # fresh-context review of the current diff
fusion runs                                   # past runs
fusion doctor                                 # which harnesses are installed and logged in
fusion smoke                                  # end-to-end self-test on a throwaway repo (~1 min, a few cents)
```

Full documentation: https://github.com/andrewsiah/openfusion
