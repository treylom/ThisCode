# Rules INDEX — situational rule router (progressive disclosure)

> **Why this file exists**: front-loading every rule into `CLAUDE.md`/`AGENTS.md`/
> `soul.md`/memory bloats context → recall drops ("the bot can't keep it all in
> mind"). Only this INDEX is always loaded; **when a trigger matches, Read that
> one rule file then** and apply it. Rule bodies live in `rules/<topic>.md`.
>
> **Loading reality (measured 2026-07-07 upstream)**: recent Claude Code
> versions auto-inject the entire `.claude/rules/*.md` directory as project
> instructions at session start — for Claude sessions this INDEX therefore acts
> as an *attention router* over rules already in context, not a lazy-load
> gate. Codex (and other harnesses that do not auto-load the rules directory) keep the original
> progressive-disclosure behavior: Read the matched rule file on trigger.
> Front-loading is an accepted trade-off on large-context models; if your
> model context is small, move rules out of the auto-loaded directory and rely
> on this INDEX alone.
> Full convention + the Claude Code / Codex variants: [rules-system.md](../docs/rules-system.md) (shipped in this repo; the ThisCodex companion ships the matching copy).
>
> **How to use (self-check every turn)**: scan the trigger table below → if a
> row matches the current situation, Read that row's rule file → apply it. No
> match → proceed. `CLAUDE.md`/`AGENTS.md` point ONLY at this INDEX (one pointer
> block, never the rule bodies).

| Trigger (when this situation) | Rule file | One-line gist |
|---|---|---|
| Replying/reporting to an external channel (Discord etc.) | [discord-comms.md](discord-comms.md) | Send via the channel reply tool; terminal output ≠ delivered. Bot mention/thread/completion gate |
| Asserting a fact / "it's empty/missing/exists" / acking a sub-agent report / about to run a count or absence check | [source-fact.md](source-fact.md) | No source → no assertion. Separate checked facts from interpretation in plain prose; don't single-grep |
| Tempted to confirm every step / about to say "done" / partial·blocked / **before starting non-due work** | [autonomy.md](autonomy.md) | Self-judge & proceed; over-confirm ❌. Proactively report completion/partial/blocked without being pinged. **Before non-due work, cross-check the day's hard events → priority counter-question (§2.7)** |
| Starting a build/design / debug / verify task / seeing the same defect recur a third time | [skill-process.md](skill-process.md) | Invoke the relevant skill BEFORE responding. Root cause before fix. Design before implement (unless user said "proceed") |
| Porting a tool/skill / deploying / pushing / adding an MCP | [porting-infra.md](porting-infra.md) | Check upstream before hand-rolling. Secret-scan before any push. MCP health-check |
| Writing a persona response (voice) | [voice.md](voice.md) | Keep the persona's voice + completion signature every response; no echo drift |
| Generating/editing/labeling images or dispatching image work | [image-ops.md](image-ops.md) | Choose edit vs generate vs overlay. Real people/brands/products are reference-first, no-imagination |
| Delegating to / waiting on a bot · asserting a bot's identity/health · multi-agent coordination · handing someone a duration estimate | [orchestration.md](orchestration.md) | Verify bot identity (chain-load guard), don't assume; teammate idle = drive not wait; meeting = adopt domain frames, no solo lock |
| Coordinating an active meeting / dispatch verification / Stop while meeting active / writing any timestamp | [meeting-protocol.md](meeting-protocol.md) | SessionStart injects active meeting + rules INDEX; verify dispatch execution; KST progress rows; Stop rereads active meeting |
| Searching the project's own KB · **before planning a task · on failure** · **before starting a task** | [knowledge-retrieval.md](knowledge-retrieval.md) | Active recall (§2): search before planning + on failure (decide, don't apologize) + propagate after. Pick tool by query shape: structured KB CLI → graph/semantic search skill → plain grep. Don't raw-grep our own docs first. **Active exploration before a task (§3): tool sweep · owner-repo sweep · expert agent + peer-agent memory (read-only)**. **Two-store routing (§1.5): conversation-memory vs curated KB — a no-hit in one store is not absence in the other.** |
| About to query KB search · a search just failed/came back empty | [search-usage.md](search-usage.md) | 3–7 word keyword queries; trust tool defaults (no per-query weight overrides). Never re-throw the same failed query — rephrase once → CLI full-text 2nd tier → plain search. Outside latency envelope = report, don't retry |
| Receiving a bug report / modifying files / about to claim "fixed" / non-trivial bug resolved | [code-quality.md](code-quality.md) | Reproduce→fix→prove; 3-step verification; don't conclude absence from limited observation; debug artifact with Detection Gap + 4-axis sibling search |
| Starting disk-heavy work · configuring a daemon's logging · ENOSPC/low-space signals | [resource-limits.md](resource-limits.md) | Pre-flight headroom ≥ max(15GB, 2× expected transient) + periodic re-measure; ENOSPC = full HOLD + alert. Verbose tracing opt-in only; daemon logs through a size-bounded rotating sink; single file >2GB = early alarm |
| Right after a major model release · ~90 days since last review · doc claims mismatch observed reality | [maintenance.md](maintenance.md) | Periodic harness review: tool claims↔reality, old rules↔new model, INDEX↔files, memory staleness, **live model↔documented model (aliases are snapshots; list every startup surface)** |

## Splitting principle
- One file = one situation cluster. Loaded on demand, so each file is focused
  and short (≈30 lines; split further if it grows).
- New rule → add it to the matching `rules/<topic>.md` (new topic → new file)
  **and** one trigger row here.
- Conflict priority: **explicit user instruction > rule file > inline default**.

## Filling these in
Each `rules/<topic>.md` here is a **generic skeleton**: a trigger, the
persona-agnostic rule shell, and a `▶ Fill in:` line for your bot/project
specifics. Adapt them; do not ship them blank — a blank fill-in does not
error, the rule just silently never fires. Walk
[FILL-IN-GUIDE.md](FILL-IN-GUIDE.md) (what each blank means, where to find the
value, filled examples, what breaks if skipped). (The §0 guided onboarding in
[docs/SETUP-CONFIG-GUIDE.md](../docs/SETUP-CONFIG-GUIDE.md) can scaffold + fill
these for you via `/prompt` + `/using-superpowers`.)
