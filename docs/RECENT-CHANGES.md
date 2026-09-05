# Recent Changes — read this on install

> Purpose: a short digest of recent behavior/contract changes so a freshly
> installed agent (and a human operator) auto-reflects them. This is a
> changelog of *what an installed bot must do differently now*, not a full
> design doc. Newest first. Plain language; first use of a jargon term is
> explained inline.

## How these reach a fresh install

Most of the items below only take effect once the hooks are wired. After
install, run the **`/thiscode:install-hooks` skill**
(`skills/install-hooks/SKILL.md`; it safely merges into
`~/.claude/settings.json`, keeping any hooks you already have). That wires:

- **SessionStart** → `hooks/bot-session-init.sh`: injects the persona
  (`soul.md`), the working-directory memory index, and the situational rules
  router `rules/INDEX.md`. ("SessionStart" = a hook Claude Code runs once when a
  session starts.) This is *why* recent `rules/` changes auto-apply — a new
  session reads the current INDEX, never a frozen copy.
- **Stop** → `hooks/meeting-stop-reread.sh`: during an active meeting, asks the
  bot to re-read the meeting progress file before it ends a turn. ("Stop" = a
  hook that runs when the model is about to stop responding.)

If hooks are not wired, the bot still runs but the items below do **not**
auto-activate. The `/thiscode:setup` skill drives this step.

---

## 2026-09-05 — ThisCode 1.4.1 documentation and ownership clarifications

- Reconciled the Korean and English manuals: ThisCode's local installer scripts
  install the selected search tools; the km plugin's `/km:search` runs the
  fallback, while `/km:setup` configures storage, MCP integrations, and
  settings without installing GraphRAG or other search tiers.
- The current km fallback order is Tier 1 GraphRAG → Tier 2 Obsidian CLI →
  Tier 3 vault-search MCP → Tier 4 ripgrep. Older entries below retain the tier
  numbering used when they were written and are historical.
- Documented the actual Codex export conditions: check mode is the default,
  and `--apply` reports an empty export only for the selected Codex layers
  outside the `repo` layer. The empty-export list remains a supported diagnostic
  result, not a removed command surface.
- Aligned public references on the `km` plugin id and marked the benchmark
  discussion as historical, with its 2026-05-13 result file as provenance.
- Clarified that `/thiscode:install-hooks` is the
  `skills/install-hooks/SKILL.md` skill entry, and kept the multi-harness
  entry documents discoverable from the package metadata.
- Updated the 1.4.1 plugin and marketplace metadata, added fail-closed
  frontmatter/version validation for contract mirrors, and expanded CI with
  positive/negative Hermes registration checks, contract-version checks, Node
  regressions, and clone-relative installer checks. Read-only installer modes
  now parse arguments before probing and do not create setup logs.

---

## 2026-09-05 — ThisCode 1.4.0 KM boundary

### Removed (no replacement)

- The `knowledge-manager-lite` and `knowledge-manager-plain` variants.
- The seven KM-family `.agents/*.yaml` registrations: `knowledge-manager`,
  `knowledge-manager-at`, `knowledge-manager-bootstrap`, `knowledge-manager-lite`,
  `knowledge-manager-plain`, `search`, and `search-lite`.
- Hermes search/ingest runtime registrations, including the former search and
  ingest tools and commands.

### Changed

- The Codex export list is now empty. The `--check` and `--apply` commands
  remain: default check mode reports "nothing to export", while `--apply`
  reports the same only when `harness` is `codex` or `both` and
  `codex_skill_layer` is not `repo`.

### Moved to the km plugin

- `knowledge-manager`, `knowledge-manager-at`, and `search`.
- `km` configuration creation is `/km:setup`.

The former ThisCode lite flow is historical; ThisCode 1.4.0 does not provide a
separate lite entry. ThisCode retains its bot-harness operations and
the local-tool installer scripts. The km plugin owns fallback execution and
storage/MCP/settings configuration; `/km:setup` does not install GraphRAG or
other search tiers.

---

## 2026-06-10 — Fresh-install audit fixes (vendored vault-search MCP + portability)

- **vault-search MCP is now vendored** at `vendor/vault-search-mcp/` and
  `scripts/install-vault-search.sh` builds it from there. The old path (git
  clone of `treylom/vault-search-mcp`) pointed at a repo that does not exist
  publicly, so a fresh **legacy Tier-2** install always failed. (The current
  contract labels vault-search MCP as Tier 3; this historical entry preserves
  its original numbering.) Registration now uses
  **`claude mcp add`** when the `claude` CLI exists (Claude Code does NOT read
  `claude_desktop_config.json`; that file is only a Claude Desktop fallback).
  The server receives your vault path via the `VAULT_PATH` env var.
- **Script root auto-detection**: `install-vault-search.sh` and
  `km-version.sh` now derive the repo root from their own location, so the
  documented plugin install path (`~/.claude/plugins/thiscode`) works without
  setting `CLAUDE_DISCODE_HOME`.
- **Discord setup docs now include Privileged Gateway Intents**: enable
  "Message Content Intent" in the Developer Portal (Bot tab) or the bot reads
  no channel messages even with a valid token. Added to
  `commands/create-bot.md`, `commands/start.md` + troubleshooting tables.
- **Generalized personal defaults**: orchestrator-only hooks now gate on
  `ORCHESTRATOR_BOT` env (was a hardcoded bot name); automation-loop bots are
  `HK_AUTOMATION_BOTS` (comma list, was hardcoded); soul templates no longer
  reference maintainer-personal skills; memory hooks honor
  `VAULT_ROOT` before the default vault path.
- **New docs**: multi-bot setup (§4.5) + knowledge-manager variant matrix
  (§4.6) in SETUP-CONFIG-GUIDE.md; "what works without Obsidian" table in
  SETUP-BEGINNER.md; `/prompt` now has a dedicated
  `Bot-Persona-Generator.md` route for drafting soul.md / CLAUDE.md.

## 2026-05-21 — README-first AI install prompt

README and setup docs now start with a copy-paste prompt for Claude Code or
Codex. The prompt tells the installing AI to read the repo docs first, proceed
step by step, ask before credentials or system-package changes, and finish with
the documented verification command.

Why it matters: a new user can paste one clear instruction into an AI assistant
instead of guessing which script to run first. The script path remains the same:
clone the repo, run the guided setup, then run `healthcheck.sh`.

## 2026-05-19 — Meeting Stop-hook output contract fixed (⑨b)

**What changed.** `hooks/meeting-stop-reread.sh` now emits the correct Stop
primitive: `{"decision":"block","reason":"<reread instruction>"}` on stdout to
extend one turn, or **empty stdout + `exit 0`** to allow the session to stop.

**Why it matters.** The Stop event has **no** `hookSpecificOutput` variant
(only `PreToolUse` / `UserPromptSubmit` / `Post*` events do). The earlier shape
was schema-rejected, so the meeting re-read was never actually injected. If you
carried an older copy, replace it. The shipped test now asserts the schema
(`decision:block`, no `hookSpecificOutput`), so a regression fails CI.

**Safety invariant.** It requests continuation only when *all* are true: bot
session, an active meeting file exists, and the Stop is not already recursive
(`stop_hook_active` guard makes it single-shot). Any other case — non-bot, no
meeting, recursion, parse failure, missing `jq` — allows stop. The hook can
never trap a session.

**Codex companion note.** On the Codex side (ThisCodex) the same hook is used,
but Codex additionally requires the hook to be **trusted via `/hooks`** (a
`trusted_hash` in `~/.codex/config.toml`) or it silently does not run even when
wired. ThisCode (Claude Code) does not need that trust step.

## 2026-05-19 — Meeting protocol rule + hooks shipped

- New `rules/meeting-protocol.md` (+ a trigger row in `rules/INDEX.md`):
  SessionStart injection contract, dispatch verification ("dispatched ≠
  working" — confirm with a concrete execution signal), append-only progress
  rows with **KST** timestamps, and the Stop-hook reread rule above.
- `hooks/bot-session-init.sh` now also injects generic active-meeting state and
  the rules INDEX (path-derived, graceful no-op when absent).

## 2026-05-1x — tmux-only setup, safe/YOLO, progress cadence (④⑥⑧)

- One-flow setup for tmux-only environments (no cmux required): aliases,
  safe-vs-YOLO mode selection, and Discord connection. "YOLO" =
  full-host-access mode; it is always an explicit opt-in, never the default.
- `/thiscode setup` is a step-by-step installer-facing skill (generated via the
  mandatory `/prompt` workflow).
- Setup now asks `progress_report_cadence`: `per_task` / `1m` / `3m` / `5m` /
  `off` / `custom`. `per_task` means a meaningful subtask or milestone
  completion — not every raw model turn boundary.

## Progressive-disclosure rules system (convention)

Operating rules live in `rules/` as a tiny always-loaded router (`INDEX.md`) +
on-demand topical files. The meta file (`CLAUDE.md`) points only at the router,
never the rule bodies — this prevents context bloat and recall decay. See
[rules-system.md](rules-system.md).
