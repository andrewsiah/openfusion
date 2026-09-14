# Devin Fusion — Research Briefing (as of 2026-09-14)

Legend: **[C]** = stated by Cognition in primary sources; **[S]** = secondary coverage; **[I]** = inference.

## 1. What Devin Fusion is

**Timeline [C]:** Announced 2026-06-29 as a preview in Devin (cognition.com/blog/devin-fusion); benchmark table on that post refreshed 2026-08-07; Fusion shipped to Devin Desktop & CLI on 2026-09-11 (cognition.com/blog/local-fusion), one day after Cognition's own SWE-2 model (2026-09-10).

**Architecture [C]:**
- Two agents run **in parallel**: a frontier "main agent"/"lead" and a cheaper "sidekick." "Both are fully capable agents with their own toolsets and ability to gather & act on their own context."
- The lead "should delegate and monitor" and "take minimal actions, and only read what is absolutely necessary," reserving for itself "the plan, the interpretation of ambiguity, the final review."
- Work is split per delegated task: the lead "hands the sidekick a brief of each task it delegates, with constraints and success criteria." "Instead of passing entire conversations between models, the lead and sidekick only exchange briefs, results, and feedback."
- Context sharing: each agent keeps a "persistent, cached context." The stated motivation is prompt-cache economics: earlier "Smart Friend" (Cognition) and Anthropic's "Advisor" approaches re-send task context to the second model uncached, so "you pay a very expensive price."
- Dynamic mid-session switching: "lightweight classifiers during task execution signal when" a model change is needed, executed "during context compaction, which would trigger a cache miss anyway."
- Per-pairing tuning (Sept post): weaker sidekicks get "more prescriptive briefs"; with SWE-2 "Fable can leave more implementation details for the sidekick to figure out." They "tune how much room the sidekick has to challenge its instructions" (pushback). "Exploration needed for planning should not be delegated to a weaker sidekick."

**Not stated / inferred:**
- No separate reviewer/verifier model is described; review is a lead responsibility **[C]**. Whether "final review" uses fresh context is unstated; Cognition's April 2026 post argues reviewers *should* have fresh context, so this is plausible but unconfirmed **[I]**.
- The posts describe *one* sidekick, not a pool of parallel workers; there is no description of a merge step. Secondary coverage (eesel) says the sidekick "explores code, writes tests, fixes lint, and performs broad edits" **[S]**.
- Failure handling/retry: the June post has no explicit text on what happens when the sidekick fails. eesel describes classifiers escalating struggling sidekick tasks to the lead **[S]**; a reasonable reading of the classifier + compaction mechanism **[I]**, but Cognition never says "retry" or "escalate."
- Internal names for the classifier, brief format, or sidekick prompt are not published.

## 2. Claimed results

**FrontierCode (Cognition's own benchmark, "mergeability" scored by tests + rubrics + verifiers; launched 2026-06-08):**
- June 29 table (per eesel's reproduction) **[S]**: Fusion 47.9 @ $2.38/task vs Opus 4.8 48.8 @ $3.24, GPT-5.5 44.8 @ $3.64, Fable 5 (medium) 57.0 @ $5.12 → the launch headline "35% cheaper at frontier quality," "41% with Fable 5 as main agent" **[C]**.
- Updated 8/7/2026 table (FrontierCode 1.1 Extended) **[C]**: Fusion 63.1 @ **$1.35** vs Fable 5 (xhigh) 64.9 @ $10.53 (→ "60% lower cost" headline — note this compares against xhigh, not against the cheaper Opus 5 medium at 63.6 @ $3.51), GPT-5.6 Sol 58.7 @ $3.41, Kimi K3 58.2 @ $3.12, Grok 4.5 56.6 @ $1.09. The score scale shift (47.9→63.1) reflects a benchmark version change, not a Fusion improvement **[I]**.

**Per-task examples [C]:** "Modernize search.js to ES6" −62% cost ($3.55→$1.37), score 98→100; "Rip out OpenTracing" −32%, 98→97; "JSON-Schema oneOf-with-const" −38%, 54→50; a React/Redux feature: −28% cost but large quality loss (54→27 per eesel) — Cognition's own example of delegation losing "subtle intent."

**Sept 11 evals (Cognition says run with Artificial Analysis and Vals AI) [C]:**

| Benchmark | Lead | Solo | Fusion + SWE-2 | Δ cost |
|---|---|---|---|---|
| DeepSWE 1.1 | Fable 5.1 | 64.3 @ $14.63 | 63.1 @ $7.88 | −46% |
| DeepSWE 1.1 | GPT-6 Astra | 67.6 @ $7.88 | 67.3 @ $4.69 | −40% |
| Terminal-Bench 4 | Fable 5.1 | 57.6 @ $17.46 | 56.1 @ $13.37 | −23% |
| Terminal-Bench 4 | Astra | 55.6 @ $10.08 | 50.0 @ $6.06 | −40% |
| SWE-Atlas QnA | Fable 5.1 | 64.8 @ $7.57 | 65.9 @ $5.00 | −34% |
| Vals Code Migration | Fable 5.1 | 54.6 @ $70.97 | 57.3 @ $42.00 | −41% |
| Vals Code Migration | Astra | 67.7 @ $44.36 | 61.3 @ $35.51 | −20% |
| FrontierCode 1.1 Ext | Fable 5.1 | 63.6 @ $2.68 | 63.5 @ $1.67 | −38% |
| FrontierCode 1.1 Ext | Astra | 63.1 @ $2.62 | 63.4 @ $2.34 | −11% |

Artificial Analysis Coding Agent Index v1.5 **[C]**: Claude Code (Fable 5.1) 62.2 @ $12.36; Fusion (Fable 5.1+SWE-2) 61.7 @ $7.90 (−36%); Codex (Astra) 61.6 @ $7.47; Fusion (Astra+SWE-2) 58.9 @ $4.54 (−39%).

**Pairings tested [C]:** Leads: Opus 4.8, GPT-5.5, Fable 5 (June); Fable 5.1, GPT-6 Astra (Sept). Sidekicks: SWE-2 (recommended; Kimi-K3-based, $0.75/Mtok) vs GPT-5.6 Luna ($0.20/Mtok) — SWE-2 gave 63.4 @ $2.34 vs Luna 62.0 @ $2.39, their argument for "price per task rather than price per token." **Production claim:** "88% of [internal users'] merged PRs were driven entirely by the automated Fusion router."

**Latency/speed:** No latency or wall-clock claims in either Cognition post **[C]**. Quality drops are small but consistently negative for Astra leads (TB4 −5.6, Vals −6.4) **[I]**.

## 3. Cognition's published write-ups and design insights

- **Devin Fusion (06-29)** and **Fusion in Desktop & CLI (09-11)** — blog posts only; no paper. Key theses **[C]**: (a) conventional routing "sucks" because routers overfit benchmarks and lose "real frontier intelligence"; (b) one-shot routing fails because prompts lack complexity signals, so routing must be dynamic; (c) tool-style advisor calls break prompt caching, hence two persistent parallel contexts; (d) the lead must stay hands-off and read minimally; (e) briefs carry constraints + success criteria; (f) evaluate on cost per task. Frontier model quality matters for the *lead*: "Fable delegates work more intelligently, requests context more efficiently, and plans more precisely."
- **Multi-Agents: What's Actually Working (04-22, Walden Yan)** **[C]**: single-threaded writes with auxiliary intelligence work; parallel-writer swarms don't; reviewers should have fresh context; the hard problem in "smart-friend" setups is an asymmetrically weaker primary that can't tell when to escalate — "a training problem." Fusion inverts this by making the *strong* model primary **[I]**.
- **SWE-2 (09-10)** **[C]**: RL post-train of Kimi K3, three effort levels; 50.0 FrontierCode Main.

## 4. Prior and related work

- **Aider architect/editor (2024-09-26):** architect describes, editor formats edits. o1-preview + DeepSeek/o1-mini (whole) 85.0% SOTA; Sonnet self-paired 80.5% vs 77.4% solo. **Polyglot (2025-01-24):** R1 architect + Sonnet editor 64.0% @ $13.29 vs o1 solo 61.7% @ $186.50 (14× cheaper). Key difference from Fusion: aider's editor is a single stateless step, not a tool-using agent **[I]**.
- **Anthropic multi-agent research system (2025-06):** Opus 4 lead + Sonnet 4 subagents beat single Opus by 90.2% at ~15× tokens; lesson: subagents need objective, output format, tool guidance, boundaries. **Anthropic Advisor Strategy (2026-04-09):** cheap executor consults Opus via tool; Sonnet+Opus +2.7pp on SWE-bench Multilingual at −11.9% cost. Fusion is the inverse (strong lead, cheap executor) and explicitly critiques Advisor's caching **[C]**.
- **Claude Code subagents:** isolated contexts, per-subagent `model:`, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`, up to 20 concurrent, 3 nesting levels. **Codex subagents:** GA 2026-03-14; `default_subagent_model`, per-agent `model` and reasoning effort.
- **Kimi K2.6 Agent Swarm:** RL-trained orchestrator (PARL), up to 300 same-model subagents. **Sakana Fugu (2026-06):** a trained orchestrator model routing over a pool of frontier LLMs.
- **Papers:** *AgentCARD* (arXiv 2606.20629): planner/executor/verifier with mixed models; up to +44% accuracy at equal cost or 12× lower cost. *PEAR* (2510.07505): a weak planner hurts more than a weak executor — consistent with Fusion keeping the frontier model as planner **[I]**. HyperAgent (2409.16299): planner/navigator/editor/executor roles.

## 5. Existing OSS "Fusion-style" orchestration across CLI agents

| Project | One-liner | What it lacks vs Fusion |
|---|---|---|
| claw-orchestrator | Runs Claude Code/Codex/OpenCode as one runtime; Planner/Coder/Reviewer "Autoloop" with independent engine per role | No dynamic switching; no shared-cache design; role split fixed per loop |
| awslabs cli-agent-orchestrator | Supervisor delegates to specialist CLIs in tmux | No cost-aware routing, no built-in verification |
| oh-my-claudecode | 19 agents, Opus orchestrator + Sonnet/Haiku workers, Ralph mode | Claude-only; static per-agent model map |
| ccswarm | Rust; plan → consensus → implement → review → fix with worktrees | Static roles, no cost measurement |
| claude-squad / vibe-kanban / Paseo | Parallel session runners / kanban UIs over multiple CLIs | Human is the orchestrator; no model-to-model delegation |
| Ralph loops | Re-feed one prompt until done | Single agent, no planner/executor split |
| Aider architect mode | Two-model reason/edit | Non-agentic editor |

**Gap [I]:** none combines (a) a persistent frontier lead that only briefs/reviews, (b) a persistent tool-using cheap executor with its own cache, (c) classifier-triggered switching at compaction, and (d) per-task cost accounting. claw-orchestrator is the closest.

## Sources
- https://cognition.com/blog/devin-fusion
- https://cognition.com/blog/local-fusion
- https://cognition.com/blog/swe-2
- https://cognition.com/blog/multi-agents-working
- https://cognition.com/blog/frontier-code
- https://www.eesel.ai/blog/devin-fusion-review
- https://halmob.com/blog/devin-fusion-cognition-hybrid-model-agentic-coding-harness
- https://aider.chat/2024/09/26/architect.html
- https://aider.chat/2025/01/24/r1-sonnet.html
- https://www.anthropic.com/engineering/built-multi-agent-research-system
- https://claude.com/blog/the-advisor-strategy
- https://code.claude.com/docs/en/sub-agents
- https://learn.chatgpt.com/docs/agent-configuration/subagents
- https://www.kimi.ai/help/agent/agent-swarm
- https://sakana.ai/fugu/
- https://arxiv.org/abs/2606.20629 · https://arxiv.org/abs/2604.17009 · https://arxiv.org/abs/2510.07505
- https://github.com/andyrewlee/awesome-agent-orchestrators
- https://github.com/Enderfga/claw-orchestrator · https://github.com/awslabs/cli-agent-orchestrator · https://github.com/yeachan-heo/oh-my-claudecode · https://github.com/nwiizo/ccswarm · https://github.com/BloopAI/vibe-kanban
