# AI Usage Guidelines — Lotrek Dev Team

> **Living document:** model list & prices are updated in the Friday Copilot review; full pass quarterly.
>
> Scope: GitHub Copilot Business (IDE completions, chat, agent mode), Gemini via our Google Workspace (Business Standard), and personal AI accounts. Quality and privacy rules apply to any AI tool.

## 🧭 TL;DR — right tool for the job

| Task | Use | Cost |
|---|---|---|
| Routine code while typing | Copilot **completions / next edit suggestions** | Free, unlimited |
| Quick code question, small edit | Copilot **chat** on a cheap model | Credits (small) |
| Multi-file implementation | Copilot **agent mode**, tightly scoped | Credits (can be large) |
| Research, comparing libraries/approaches | **Gemini app** (+ Deep Research) | Already paid in Workspace |
| Docs, specs, emails, meeting notes | **Gemini** (app or Docs/Gmail side panel) | Already paid in Workspace |
| Project knowledge base / onboarding Q&A | **Gemini Notebook** (NotebookLM) | Already paid in Workspace |
| Anything with client code on a **personal** AI account | — | Never |

---

## 1. 💳 How Copilot billing works (since June 2026)

Premium requests are gone. Copilot is billed in **GitHub AI Credits**: 1 credit = $0.01, metered on the **actual tokens** you consume (input + output; cached input at ~10% of the input price), priced per model. ([Official docs](https://docs.github.com/en/copilot/concepts/billing/usage-based-billing-for-organizations-and-enterprises))

What this means for us on Copilot Business:

- **1,900 credits ($19) per user per month** — promotional 3,000 until Sept 1, 2026 — **pooled across the whole org**. There is no personal quota: a credit spent by anyone comes out of everyone's pool. No rollover; resets on the 1st of each month (UTC).
- **Free and unlimited:** code completions and next edit suggestions. They never touch the pool.
- **Billed:** every chat prompt (ask / edit / agent / plan modes), proportional to model price and tokens.
- **Our overage policy is "hard block":** when the pool is empty, chat and agent mode stop working *for the entire team* until the 1st. Completions keep working. There is no fallback to a cheaper model — GitHub removed the "included model" tier entirely.

The key mental shift from the old premium-request world: a prompt no longer has a flat price. **Context is the bill.** A short question to a small model costs a fraction of a credit; a long agent session on a frontier model with half the repo attached costs hundreds.

For scale: the standard allowance works out to roughly **90 credits (~$0.90) per person per working day**. One exchange with ~100k tokens of attached context on a frontier model can eat more than a day's share in a single prompt (see §5).

## 2. 💸 Cost discipline

Habits, in order of impact:

1. **Completions first.** They're free. Lean on them (and next-edit suggestions) for routine code, boilerplate, tests-by-example. Reach for chat only when completions can't get there.
2. **Right-size the model.** The price spread between the cheapest and most expensive enabled model is ~40×. Default to the cheap tier for everyday questions and mechanical edits; escalate to a frontier model deliberately, for genuinely hard problems — and note that false economy is real: three failed retries on a cheap model cost more than one clean answer from a mid model. Bring these cases to the Friday review.
3. **Context discipline.** Attach the files that matter, not the workspace. Start a **new chat per task** — every turn re-sends the conversation history as input tokens (caching softens this to ~10%, but a bloated thread still leaks credits on every message).
4. **One good prompt beats five vague ones.** Retries are re-billed in full. State the goal, the constraints, the relevant files, and what "done" looks like. This is also why repo instruction files exist (§8).
5. **Agent mode is a power tool, not the default.** It bills every token of its autonomous iterations. Use it for genuinely multi-file work with clear acceptance criteria; watch it; stop a session that's flailing. A one-file change is a chat edit or a completion, not an agent run.
6. **Keep the extras off by default.** Higher reasoning settings and the extended (1M-token) context window multiply token burn. Turn them on for a specific reason, then back off.
7. **Offload everything that isn't code to Gemini** (§3). Research, comparisons, drafts, brainstorming an approach *before* implementing it — all zero marginal cost. Think with Gemini, implement with Copilot.
8. **Glance at your consumption before Friday.** Come to the review knowing what you spent and on which models.

## 3. ✨ Gemini — already paid for, use it more

Our Workspace Business Standard includes, per person: the **Gemini app** (gemini.google.com) with Gems, ~25 Pro-model prompts per 4 hours and 300 Thinking-model prompts/day, **20 Deep Research reports/day**, Gemini in the Gmail/Docs/Sheets/Drive side panels, and **Gemini Notebook** (NotebookLM). ([Limits](https://support.google.com/gemini/answer/14620100))

This is the zero-marginal-cost half of our stack. Default to it for:

- Technology research and library comparisons (Deep Research is genuinely good for "compare X vs Y for our use case" and costs zero Copilot credits).
- Architecture rubber-ducking before you spend Copilot credits implementing.
- Drafting docs, specs, client emails, estimates, meeting notes.
- Gemini Notebook as a per-project knowledge base (specs, call notes, docs — then ask questions against it).

**Data protection — the one rule that matters:** Gemini used **while logged into your Lotrek Workspace account** is a core Workspace service under the Cloud Data Processing Addendum: prompts are Customer Data, not human-reviewed, not used to train models. Work content is fine there. ([Privacy Hub](https://support.google.com/a/answer/15706919))

These are **not** the same thing and are **not** covered: personal-account gemini.google.com, Google AI Studio, and the free Gemini API tier — all of those can use your content for training and human review. If you're in the Gemini app, check which account you're logged into.

(There is no Gemini in the IDE: Gemini Code Assist was never part of Workspace, and its free tier was discontinued in June 2026. IDE work is Copilot's job.)

## 4. 📅 The Friday review

Our weekly Copilot usage review is the governance mechanism for everything time-sensitive in this document. It's where we:

- **Decide which models are enabled** in the Copilot settings panel. The enabled list is a team decision, made there — this document deliberately doesn't contain one.
- **Check the pool's pace**: consumed credits vs. day of month. If we're on track to hit the hard block, agree on what to throttle.
- **Review per-user and per-model consumption** — not to police, but to find patterns worth copying ("this model did the job at a tenth of the price") or fixing ("this workflow burns credits for nothing").
- **Share model experience**, including false-economy cases where a cheap model wasted more than it saved.
- **Update the snapshot table below** when GitHub changes models or prices.

## 5. 🏷️ Model prices — examples only

⚠️ **Every model named in this document is an example, not a recommendation.** Which models are enabled — and which we prefer for what — is decided week by week in the Friday review; this table only gives a sense of scale. Prices verified 2026-07-20 against [GitHub's pricing page](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing) — **update in the Friday review**. Per 1M tokens, input/output:

| Tier | Model | Input | Output |
|---|---|---|---|
| Economy | GPT-5 mini | $0.25 | $2.00 |
| Economy | Gemini 3 Flash | $0.50 | $3.00 |
| Economy | Claude Haiku 4.5 | $1.00 | $5.00 |
| Mid | Claude Sonnet 5 *(promo to Aug 31, 2026)* | $2.00 | $10.00 |
| Mid | Gemini 3.1 Pro | $2.00 | $12.00 |
| Mid | GPT-5.4 | $2.50 | $15.00 |
| Mid | Claude Sonnet 4.6 | $3.00 | $15.00 |
| Frontier | Claude Opus 4.8 | $5.00 | $25.00 |
| Frontier | GPT-5.5 | $5.00 | $30.00 |
| Frontier | Claude Fable 5 | $10.00 | $50.00 |

Concrete anchor (using two of the example models above): a single exchange with 100k input tokens and 5k output costs **~125 credits on Claude Fable 5** vs. **~3.5 credits on GPT-5 mini** — a day-and-a-half of one person's allowance vs. pocket change, for the same prompt.

## 6. 🔒 Privacy & client code

| Where | Client code / work content? | Why |
|---|---|---|
| Copilot Business (our org seats) | ✅ Yes | Contractually excluded from model training under GitHub's DPA |
| Gemini, logged into Lotrek Workspace | ✅ Yes | Core service under the CDPA — no training, no human review |
| Google AI Studio / free Gemini API / personal Gemini | ❌ No | Free tiers train on content and allow human review |
| Personal AI accounts (any provider) | ❌ Never | See below |

Rules:

- **Secrets never go in a prompt.** No credentials, tokens, client PII — in any tool, including the approved ones. Reference env vars, don't paste values.
- **Personal accounts are for generic learning only.** No client code, no internal data, nothing identifying a client. Know the defaults you're dealing with: ChatGPT and personal Gemini train on conversations by default (opt-out); **Copilot Individual plans also train by default since April 2026** (our Business seats do not — one more reason to work signed into the org account, not a personal one); Claude asks at signup. If you use a personal account at all, disable training in its settings.
- **Client contracts:** none currently restrict AI usage. If you ever spot an AI/ML clause in a client agreement, raise it with the team before using AI on that project.

## 7. ✅ Quality gates

AI-generated code is held to exactly the bar as hand-written code — no higher ceremony, no lower scrutiny.

- **You own what you ship.** Never commit a line you can't explain. "Copilot wrote it" is not a review response.
- **Same review bar.** AI code goes through the same PR review as everything else; large generated chunks are worth a note in the PR description so the reviewer knows where to slow down.
- **Non-trivial generated logic gets a test.** Especially the code that looks finished — plausible-but-wrong is the signature AI failure mode.
- **Extra scrutiny on sensitive paths**: auth, permissions, input validation, payments, crypto. Treat AI output there as a draft from an intern who read the docs once.
- **Commit hygiene unchanged**: Conventional Commits, and PR descriptions that describe the actual diff.

## 8. 🗂️ Repo setup standard

Well-configured repos make every AI interaction better *and* cheaper: GitHub's own guidance confirms good custom instructions raise first-attempt quality — and fewer retries is the biggest credit saver there is.

Every active repo gets:

1. **`AGENTS.md` at the root — the canonical, tool-agnostic agent guide.** Dev commands, conventions, repository map, gotchas. Use [camomilla's AGENTS.md](https://github.com/camomillacms/camomilla-core/blob/master/AGENTS.md) as the reference example. This one file serves Copilot, Claude Code, Cursor, and whatever comes next.
2. **VS Code wired to read it:** commit `.vscode/settings.json` with `"chat.useAgentsMdFile": true` so Copilot chat and agent mode load it automatically.
3. **`.github/copilot-instructions.md` as a thin pointer** (a 3-line summary + "see AGENTS.md"), since it's the most widely supported instruction type across Copilot surfaces. ⚠️ Verified gotcha: Copilot has **no `@file` import syntax** — that's a Claude Code feature. Don't try to import AGENTS.md from it; the line would be read as plain text. Keep it thin instead of duplicating content.
4. **Keep instruction files lean.** They're prepended to *every* request — under token billing, a bloated instructions file is a tax on every single prompt, org-wide.
5. Where useful: path-scoped rules in `.github/instructions/*.instructions.md` (`applyTo` globs, good for monorepos) and reusable prompts as `.github/prompts/*.prompt.md` slash commands for recurring tasks.

## 📚 Sources

All facts above verified 2026-07-20 against: GitHub docs on [usage-based billing](https://docs.github.com/en/copilot/concepts/billing/usage-based-billing-for-organizations-and-enterprises), [models & pricing](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing), [custom-instructions support matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support), and [Copilot training-data policy](https://docs.github.com/en/copilot/how-tos/manage-your-account/manage-policies); Google's [Workspace generative-AI Privacy Hub](https://support.google.com/a/answer/15706919) and [Gemini limits per edition](https://support.google.com/gemini/answer/14620100); [Gemini API terms](https://ai.google.dev/gemini-api/terms); [OpenAI data-usage FAQ](https://help.openai.com/en/articles/5722486); [Anthropic privacy docs](https://privacy.claude.com/en/articles/10023580); [Google Gemini Apps privacy](https://support.google.com/gemini/answer/13594961).
