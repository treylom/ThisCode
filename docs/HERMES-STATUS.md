# Hermes plugin — status: runtime subset / deferred

> Decision: maintainer, 2026-05-16, option ② (redesign to current structure +
> document deferred — do **not** reconstruct the missing dispatchers).

## TL;DR

The `hermes-plugin/` metadata advertises the broader ThisCode Claude Code
surface, while `hermes-plugin/__init__.py` deliberately registers only the
session-start drift-check hook at runtime. Knowledge management and vault
search belong to the km plugin.

## What works (active)

| Piece | State |
|---|---|
| Runtime registration (`__init__.py`) | ✅ session-start drift-check hook registers cleanly |
| `session_start_drift_check` | ✅ real — shells out to `scripts/km-version.sh` (exists) |
| `plugin.yaml` metadata / agent-spec aggregation | ✅ manifest remains the source for the Claude Code surface |

## What is deferred (and why)

| Manifest-only surface | State | Why |
|---|---|---|
| `claude_discode_bootstrap` | ⏸️ deferred | declared for the Claude Code/plugin surface; no Hermes runtime handler in 1.4.0 |
| `claude_discode_meetings` | ⏸️ deferred | declared for the Claude Code/plugin surface; no Hermes runtime handler in 1.4.0 |
| `claude_discode_codex_invoke` | ⏸️ deferred | declared for the Claude Code/plugin surface; no Hermes runtime handler in 1.4.0 |
| `claude_discode_shared_memory` | ⏸️ deferred | declared for the Claude Code/plugin surface; no Hermes runtime handler in 1.4.0 |
| `claude_discode_route_model` | ⏸️ deferred | declared for the Claude Code/plugin surface; no Hermes runtime handler in 1.4.0 |
| `/thiscode:setup` | ⏸️ deferred | declared for the Claude Code/plugin surface; no Hermes runtime command in 1.4.0 |
| `on_stop` | ⏸️ deferred | declared for the Claude Code/plugin surface; no Hermes runtime hook in 1.4.0 |

**Root cause (verified 2026-05-16, independent cross-validation):** ThisCode's
portable skills are **LLM-instruction documents** (`SKILL.md` + `references/*.md`)
and the manifest describes Claude Code surfaces. Hermes does not receive
programmatic implementations for those manifest-only surfaces in 1.4.0, so
the runtime stays limited to the drift-check hook instead of pretending that
metadata entries are live registrations.

## Current behavior (honest, non-failing)

- `register(ctx)` registers only `on_session_start`; no removed KM/search
  runtime tools or commands are exposed by Hermes.
- The manifest-only surfaces above remain visible for host metadata and are
  explicitly deferred rather than represented as live Hermes registrations.

## Supported path instead

Use thiscode through **Claude Code** (or any LLM agent that reads `SKILL.md`):

- Install the km plugin (`claude plugin marketplace add treylom/tofukyung-plugins`
  + `claude plugin install km@tofukyung-plugins`) and use its search and
  knowledge commands — `/km:search` for the documented fallback.

## How to un-defer (future)

To expose a manifest-only surface in Hermes, implement and register a handler
for that surface, add its schema where needed, and update the runtime-manifest
test plus this deferred table in the same change.
