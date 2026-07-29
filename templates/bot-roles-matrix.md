# Bot Roles Matrix — template (added 2026-07-29)

> One page answering "which bot owns this work, and how do I address it".
> Commissioned pattern: role ambiguity and stale per-bot docs were a recurring
> failure source; a single measured matrix with IDs closed it.

## Principles (keep these when filling in)

1. **Single SoT for identity values** — bot user IDs come from your roster
   file (extracted from bot tokens, never guessed). This matrix *cites* the
   roster; it does not fork it.
2. **Minimize value duplication** — every duplicated value (counts, models,
   channel IDs) eventually diverges. Prefer pointers to the owning document;
   keep only the columns agents need at dispatch time.
3. **Record observed mismatches instead of silently fixing** — when a bot's
   own doc disagrees with measured reality, log both values with an as-of
   date; the doc's owner fixes their surface.
4. **Snapshot honesty** — model/runtime columns are as-of snapshots; note the
   date and how to re-measure (e.g. session transcript's model field).

## 1. At a glance — task → owner

| If the task is… | 1st owner | Note |
|---|---|---|
| (e.g. orchestration / policy / meetings) | BOT_A | coordinates, does not take over work |
| (e.g. fact-check / cross-verification) | BOT_B | two independent sources minimum |
| (e.g. schedule / watchdog / completion intake) | BOT_C | domain owner, not a worker |
| … | … | … |

## 2. Full matrix — one row per bot

| Bot | user_id (mention) | Direct channel | Core domain | Boundaries (must NOT do) |
|---|---|---|---|---|
| BOT_A | `<numeric id from roster>` | `<channel id or "mention-only">` | … | … |
| BOT_B | `<numeric id>` | mention-only | … | … |

▶ Fill in: one row per bot from your roster file. `user_id` is what `<@id>`
mentions use — a wrong ID is a silent drop, so copy from the roster, never
from memory.

## 3. Known mismatches (observed — do not silently reconcile)

| # | Surface A (value) | Surface B (value) | As-of | Owner to fix |
|---|---|---|---|---|
| 1 | … | … | YYYY-MM-DD | … |
