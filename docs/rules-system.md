# Rules System — Progressive-Disclosure agent rules (no context bloat)

> Convention shipped with ThisCode / ThisCodex. Origin: 운영자 spec 2026-05-16 — "규칙을 CLAUDE.md/soul.md/메모리에 많이 넣으면 다 기억 못 함. rules.md 신설해 상황별 참조." Verified in the obsidian-ai-vault deployment (`.claude/rules/`).

## Problem

Front-loading every operational rule into the always-loaded context (`CLAUDE.md` / `AGENTS.md` / `soul.md` / auto-injected memory) bloats the context window. Recall degrades — the agent "knows" the rules are somewhere but does not reliably apply the right one at the right moment. Adding more rules makes it worse, not better.

## Pattern

A `rules/` directory with one small **router** + many **on-demand topical files**:

```
.claude/rules/                 (or <bot-WD>/rules/ for a Codex bot)
├── INDEX.md          ← the ONLY file referenced from always-loaded context
├── discord-comms.md  ← loaded only when about to talk to an external channel
├── source-fact.md    ← loaded only when asserting a fact / verifying
├── autonomy.md       ← loaded only when tempted to over-confirm / before "done"
│                        (also: the proactive completion/partial/blocked report
│                         gate — report on completion, partial artifact,
│                         awaiting-permission, handoff, or blocked >10–15min
│                         WITHOUT being pinged; "next step remains" is not a
│                         reason for silence. Bridge-level heartbeat backs this
│                         in code — see ThisCodex docs/yolo-bridge-contract.md)
├── skill-process.md  ← loaded only when starting a build/debug/verify task
├── porting-infra.md  ← loaded only when porting/deploying/adding MCP
├── voice.md          ← loaded only when writing a persona response
├── orchestration.md  ← loaded only when delegating to / waiting on a bot,
                         asserting a bot's identity/health, or coordinating
                         multiple agents (chain-load identity guard: a shared
                         root context file that doubles as one bot's WD meta
                         must carry a top identity guard so other bots
                         chain-loading it don't absorb that identity; teammate
                         idle = drive not wait; meeting = adopt domain frames,
                         no solo lock)
└── meeting-protocol.md ← loaded only when coordinating an active meeting,
                          verifying a bot dispatch, writing KST progress rows,
                          or stopping while a meeting is still active
```

- **`INDEX.md`** is a compact trigger table: `situation → rule file → one-line gist`. It is the only thing `CLAUDE.md`/`AGENTS.md` points to (one pointer block, not the rules themselves).
- Each turn the agent scans INDEX's triggers; when the current situation matches a row, it **Reads that one rule file then** and applies it. No match → proceed. Rules are paid for only when relevant.
- Each rule file is **focused and short** (≈30 lines; split further if it grows). One file = one situation cluster.
- Rule files **cross-link 1:1 with memory entries** (`[[memory-slug]]`). Memory = the incident/learning log (why); the rule file = the actionable spec (what to do). They are not duplicated.
- **Priority on conflict**: explicit user instruction > rule file > inline default (same as superpowers instruction-priority).

## Why this works

Progressive disclosure: the router is tiny and always present, so the agent always knows *that* a rule may apply and *where* it is — but the heavy prose is loaded only in-context-of-use, when attention is already on that situation. Recall becomes a lookup, not a memorization test.

## How to add a rule

1. Put the rule in the matching `rules/<topic>.md` (new topic → new file).
2. Add or update one trigger row in `rules/INDEX.md`.
3. If it came from a learned mistake, also write the memory entry and cross-link both ways.
4. Keep `CLAUDE.md`/`AGENTS.md` pointing only at `INDEX.md` — never inline the rule back.

## Applying to a Claude Code bot (ThisCode)

The bot's `CLAUDE.md` (auto-loaded by Claude Code) carries **only** the INDEX pointer — never the rule bodies. The `rules/` dir ships in this plugin. The on-demand discipline is the same: dynamic per-turn state is injected by hooks at SessionStart; static rules stay in `rules/` and are pulled by trigger, never re-injected per turn.

### Meeting protocol hooks

ThisCode ships hook helpers for active meetings. They become active **only after the hooks are wired** — run `/thiscode:install-hooks` (it merges into `~/.claude/settings.json`, preserving any existing hooks):

- `hooks/bot-session-init.sh` is the **SessionStart** helper. It injects soul.md
  (persona), the working-directory memory index, and — when present — the
  progressive `rules/INDEX.md` plus generic active-meeting state. Paths are
  derived from environment / `BOT_WD` / `PWD`; missing files are a graceful
  no-op. This is how recent `rules/` changes reach the model automatically: a
  fresh session reads the current INDEX, not a frozen copy.
- `hooks/meeting-stop-reread.sh` is the **Stop** helper. It emits
  `{"decision":"block","reason":...}` (the only valid Stop block+inject
  primitive — the Stop event has **no** `hookSpecificOutput` variant) only for a
  bot session with an active meeting file and a non-recursive Stop. A built-in
  recursion guard (`stop_hook_active`) makes it single-shot. Every other case
  allows stop silently (empty stdout + `exit 0`), so it can never trap a
  session.

The helpers intentionally avoid maintainer-local vault paths and Discord thread
IDs — the shipped contract is path-parameterized and fail-open.

## Applying to a Codex bot (ThisCodex)

The Codex companion ([ThisCodex](https://github.com/treylom/ThisCodex)) applies
the identical convention on the Codex side: the bot's `AGENTS.md`
(project-doc auto-loaded) carries only the INDEX pointer, and the same hook
helpers ship there. One Codex-specific operational caveat: a wired Codex Stop
hook does **not** run until it is trusted via the Codex `/hooks` flow (a
`trusted_hash` must land in `~/.codex/config.toml`). See ThisCodex's setup
skill / README for the Codex `/hooks` trust step — without it the meeting
Stop-reread is silently inactive even though the wiring exists.
