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
├── image-ops.md      ← loaded only when generating/editing images
│                        (edit vs generate vs overlay; real people/brands/
│                         products are reference-first, no-imagination)
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

### Hook scope: settings do NOT walk up (register global + guard by cwd)

Claude Code resolves *instruction* surfaces (`CLAUDE.md`, front-loaded rule files) by
walking **up** from the session's working directory — but *settings hooks* do not walk
up. A session whose WD is a **subdirectory** carrying its own `.claude/settings.json`
(a per-bot WD is the common case) loads **none** of the parent project's hooks, and
nothing signals the gap: the instruction layer keeps walking up, so the session *looks*
fully governed. Measured in production (multi-bot vault deployment, 2026-08-04,
n=6 subdirectory-WD bot sessions): hooks registered **only** in the project root
had never fired in any of them. One such hook logged 2,064 injections in root-WD
sessions over the same window against 0 in the subdirectory sessions counted; a
second logged 287 against 0 across all six. The finding is scoped to root-only
registrations — hooks that already shipped a per-WD copy fired normally.

Consequences for a deployment:

1. **Mandatory hooks belong in user-global settings** (`~/.claude/settings.json`) —
   exactly where `/thiscode:install-hooks` merges them. Never rely on a
   project-root `settings.json` to cover nested bot WDs.
2. **Globally registered hooks fire in every project**, so scope workspace-specific hooks
   with a cwd guard wrapper (generalized from the production fix):

   ```bash
   #!/bin/bash
   # scope-guard: run <hook-basename> only inside $WORKSPACE_ROOT; fail-open elsewhere.
   IN=$(cat 2>/dev/null)
   CWD=$(printf '%s' "$IN" | jq -r '.cwd // empty' 2>/dev/null)  # `// empty` — a bare `.cwd` yields the *string* "null"
   [ -n "$CWD" ] || CWD="$PWD"
   case "$CWD" in "$WORKSPACE_ROOT"|"$WORKSPACE_ROOT"/*) ;; *) exit 0 ;; esac  # exact + /* — a single "$WORKSPACE_ROOT"* glob would also match siblings like /x/myroot-backup
   B="${1##*/}"                                  # basename only — blocks path injection
   H="$WORKSPACE_ROOT/.claude/hooks/$B"
   STATE_DIR="${THISCODE_STATE_DIR:-$HOME/.claude-state}"
   if [ ! -f "$H" ]; then
     mkdir -p "$STATE_DIR" 2>/dev/null
     echo "$(date +%FT%T) MISSING_HOOK $B" >> "$STATE_DIR/scope-guard-missing.log" 2>/dev/null
     exit 0
   fi
   printf '%s' "$IN" | bash "$H"                 # relay stdin, stdout, and the exit code (deny/inject preserved)
   ```

   The production wrapper additionally falls back to a `.claude/scripts/`
   directory for hooks that live there.

3. Settings **live-reload** per hook event — but reloading applies to the files
   the session already loaded at start, not to newly discovered ones.
   `~/.claude/settings.json` is always in that set, so a new entry there reaches
   a running subdirectory session on its next event; a project-root
   `settings.json` the session never loaded stays unreachable no matter how many
   events pass. Verify a migration on both layers: a wrapper smoke test proves
   the guard, but only a **natural firing inside a real subdirectory-WD session**
   proves the settings-loading layer (the two are not substitutes).

## Applying to a Codex bot (ThisCodex)

The Codex companion ([ThisCodex](https://github.com/treylom/ThisCodex)) applies
the identical convention on the Codex side: the bot's `AGENTS.md`
(project-doc auto-loaded) carries only the INDEX pointer, and the same hook
helpers ship there. One Codex-specific operational caveat: a wired Codex Stop
hook does **not** run until it is trusted via the Codex `/hooks` flow (a
`trusted_hash` must land in `~/.codex/config.toml`). See ThisCodex's setup
skill / README for the Codex `/hooks` trust step — without it the meeting
Stop-reread is silently inactive even though the wiring exists.

## Root-instruction unification (CLAUDE.md / AGENTS.md single source)

When one deployment serves both Claude Code (auto-loads `CLAUDE.md`) and Codex-style agents (auto-load `AGENTS.md`), do not maintain two rule bodies:

- **`AGENTS.md` = the shared operational rules (SSOT)** — progressive-disclosure pointer to `rules/INDEX.md`, completion gates, core paths.
- **`CLAUDE.md` = `@AGENTS.md` import at the top** + Claude-specific blocks only (identity guard, tool wrappers).

Caveats learned in production (obsidian-ai-vault charness adoption, 2026-06-11; items 3–5 from the 2026-08-05 mirror-staleness incident):
1. A whitelist-style `.gitignore` (`*` then `!` exceptions) silently untracks a new root file — add an explicit `!/AGENTS.md`.
2. Verifying that a Codex agent actually receives the chain: echo-style probes get **contaminated** — the injected rules change the probe's own behavior. Use session-transcript forensics (inspect the injected payload in the agent's rollout log) with a read-only sandbox instead.
3. **Make the chain visible at the top of every per-bot WD instruction file.** A bot's WD `CLAUDE.md` *receives* the shared rules via chain-load, but anyone auditing just that file cannot see it — which reads as "this bot has no shared rules." Add a one-line pointer at the top ("shared rules arrive via the root `@AGENTS.md` chain-load; no duplicate `@import` here — duplicating would inject the same body twice"). A pointer costs one line; a duplicate import costs the whole rules body per session.
4. **Mirrors of live instruction files must be script-generated, never hand-copied.** If `CLAUDE.md`/`AGENTS.md`/persona files are mirrored into a human-readable wiki for owner review, the mirror must be produced by a maintained sync script — verbatim content plus an `AUTO-MIRROR` header naming the origin path. Orphan hand-made copies rot silently: in production, six hand-copied CLAUDE.md mirrors froze for 5+ weeks and the owner audited stale rules and model names as if they were current. Register every new bot's files in the sync script's mirror list as part of bot creation.
5. **Derived surfaces quote exact launch flags and name the launch SoT.** Model/effort mentions in bot docs must carry the real launch arguments (e.g. `--model 'claude-opus-5[1m]' --effort xhigh`) plus where they are launched from (shell alias, launchd plist). Alias-form snapshots (`opus[1m]`) go stale silently when the alias retargets to a new model generation.

## Enforcement: when the self-check gets skipped (rule-router + action gates)

The progressive-disclosure pattern above relies on the agent **scanning INDEX each turn** and Reading the matching rule. That scan is *soft* — under load, time pressure, or a long message chain the agent can skip it, leaving the rule unapplied ("knowledge ≠ enforcement"). Two optional, fail-open hook layers harden the high-cost rules without re-bloating always-on context:

### Layer 1 — force-surface the matching rule gate (`hooks/rule-router.sh`, UserPromptSubmit)
Rather than trusting the agent to scan INDEX, a UserPromptSubmit hook reads the prompt, matches task-type keywords, and **injects the matching rule's core gate into context right then**. The mapping mirrors INDEX's trigger table (single source — the hook keys off task-types, it does not duplicate the rule bodies). This is complementary to a static always-on self-check, which becomes tuned-out precisely because it is identical every turn; the router is situation-matched, so it is relevant and hard to ignore. fail-open: no keyword match, or no `jq`/empty prompt → emit nothing, `exit 0`.

### Layer 2 — block the detectable violation (Stop / PreToolUse action gates)
Where a rule maps to a **detectable action** (a tool call, a Stop, an outbound deliverable), a Stop or PreToolUse hook checks for the violation signal and blocks with a one-line reminder (Stop blocks via `{"decision":"block","reason":...}`). Shipped examples: `completion-gate.sh` (pre-report before declaring "done" to the user), `dispatch-verify.sh` (verify a delegated bot actually started before ending the turn), `reply-gate.sh` (deliver via the channel tool, not terminal-only).

### Discipline (avoid over-hardening)
- Put hooks only on **costly, repeatedly-skipped** rules — never on the soft judgment/draft space (over-hooking = false positives = the agent fights its own harness). Mirror the autonomy gradient: read/draft = free, commit = self-judge, deploy/public = multi-party.
- **fail-open is non-negotiable** (uncertainty → allow): a buggy gate degrades to a no-op, never a session trap. Recursion-guard every Stop gate (`stop_hook_active`).
- Ship each gate with a **block-case + allow-case test** before wiring.
- Transcript-scanning Stop gates miss events summarized away by context **compaction** → carry an escape clause ("if already satisfied / not applicable, ignore and stop"); detection should key off filenames/structured fields, not free-text keywords (which false-fire on progress reports).

Origin: obsidian-ai-vault 2026-06-29 — a soft INDEX self-check was being skipped under load; `rule-router` (Layer 1) + action gates (Layer 2) were added. The router is the broad fix ("rules not read"); action gates are the targeted fix ("rule read but not obeyed").
