# Rules INDEX — situational rule router (progressive disclosure)

> **Why this file exists**: front-loading every rule into `CLAUDE.md`/`AGENTS.md`/
> `soul.md`/memory bloats context → recall drops ("the bot can't keep it all in
> mind"). Only this INDEX is always loaded; **when a trigger matches, Read that
> one rule file then** and apply it. Rule bodies live in `rules/<topic>.md`.
> Full convention + the Codex-bot variant: [rules-system.md](https://github.com/treylom/ThisCodex/blob/master/docs/rules-system.md) (canonical, in the ThisCodex companion repo).
>
> **How to use (self-check every turn)**: scan the trigger table below → if a
> row matches the current situation, Read that row's rule file → apply it. No
> match → proceed. `CLAUDE.md`/`AGENTS.md` point ONLY at this INDEX (one pointer
> block, never the rule bodies).

| Trigger (when this situation) | Rule file | One-line gist |
|---|---|---|
| Replying/reporting to an external channel (Discord etc.) | [discord-comms.md](discord-comms.md) | Send via the channel reply tool; terminal output ≠ delivered. Bot mention/thread/completion gate |
| Asserting a fact / "it's empty/missing/exists" / acking a sub-agent report | [source-fact.md](source-fact.md) | No source → no assertion. Label SOURCE FACT/INFERENCE/UNCERTAINTY; cross-check, don't single-grep |
| Tempted to confirm every step / about to say "done" / partial·blocked | [autonomy.md](autonomy.md) | Self-judge & proceed; over-confirm ❌. Proactively report completion/partial/blocked without being pinged |
| Starting a build/design / debug / verify task | [skill-process.md](skill-process.md) | Invoke the relevant skill BEFORE responding. Root cause before fix. Design before implement (unless user said "proceed") |
| Porting a tool/skill / deploying / pushing / adding an MCP | [porting-infra.md](porting-infra.md) | Check upstream before hand-rolling. Secret-scan before any push. MCP health-check |
| Writing a persona response (voice) | [voice.md](voice.md) | Keep the persona's voice + completion signature every response; no echo drift |
| Delegating to / waiting on a bot · asserting a bot's identity/health · multi-agent coordination | [orchestration.md](orchestration.md) | Verify bot identity (chain-load guard), don't assume; teammate idle = drive not wait; meeting = adopt domain frames, no solo lock |
| Searching the project's own knowledge base / notes / docs | [knowledge-retrieval.md](knowledge-retrieval.md) | Pick tool by query shape: structured KB CLI → graph/semantic search skill → plain grep. Don't raw-grep our own docs first |

## Splitting principle
- One file = one situation cluster. Loaded on demand, so each file is focused
  and short (≈30 lines; split further if it grows).
- New rule → add it to the matching `rules/<topic>.md` (new topic → new file)
  **and** one trigger row here.
- Conflict priority: **explicit user instruction > rule file > inline default**.

## Filling these in
Each `rules/<topic>.md` here is a **generic skeleton**: a trigger, the
persona-agnostic rule shell, and a `▶ Fill in:` line for your bot/project
specifics. Adapt them; do not ship them blank. (The §0 guided onboarding in
[docs/SETUP-CONFIG-GUIDE.md](../docs/SETUP-CONFIG-GUIDE.md) can scaffold + fill
these for you via `/prompt` + `/using-superpowers`.)
