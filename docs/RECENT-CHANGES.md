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

## 2026-11-11 — ThisCode 1.5.0 three automatic attempts before a hand-off, per-step automation tables, Korean screen names, developer-terms question, three wider bot permissions only on a yes, token saved outside the chat

- When a step gets stuck, the bot no longer hands it to the user right away.
  It tries three times on its own with the automation browser (read the screen
  again and retry → another way in the same browser → the next browser),
  records each attempt, and asks `scripts/install-gate.sh --handoff <gate>`
  before handing over. Human-only stops (login, the human check, a password, a
  permission prompt) are handed over at once and are not counted.
  The attempt lines are a procedure record the bot writes itself; the script
  cannot check that the browser was really driven three times.
- Every skill with `### Step` headings ships an `automation.yaml`: for each step, `auto`,
  `auto_then_human` or `human_only`, the gate name, and the text shown when a
  step is handed over. A test fails when the table and the SKILL.md step
  headings differ. In create-bot, the portal, new-application and token steps
  also have `handoff_after_attempts`, the text used after three failed
  attempts.
- New-application window of the Discord developer portal: the bot asks a
  yes/no question before the developer-terms box. Only after a yes does it tick
  the box and click Create. After a no it clicks nothing and waits for the user
  to do both; with no answer it clicks nothing. The box does not show up in the
  page text, so when Create stays disabled the bot counts the input elements in
  the window to find it.
- Discord developer-portal buttons and windows are also named in Korean where
  the Korean label was seen on a real Korean-language screen ("New
  Application" = «신규 애플리케이션»); labels not yet seen in Korean stay in
  English and are marked unconfirmed.
- The bot invite link keeps the 11 default permissions
  (`permissions=395137117248`). Before the link is made the bot names three
  wider ones — Mention Everyone, Pin Messages, Manage Webhooks — says what each
  lets the bot do, and asks once. Only a yes adds them
  (`permissions=2252195487804480`), and the 14 chosen permissions are shown
  before the link is made. No answer, a no, or anything else keeps the 11.
- The bot token is never taken through the conversation: the bot presses the
  portal's Copy button, and one script, `scripts/discord-token-capture.sh`,
  moves the token from the clipboard into the bot's `.env` without showing
  it. How it does that:
  - `arm <bot>` puts a fresh
    one-time marker in the clipboard and notes it for that bot, the Copy button
    is pressed, and `capture <bot>` — only if that bot was armed within the last
    10 minutes — checks the marker and the shape, writes a 0600 `.env`, empties
    the clipboard and prints the length and the file path, never the value.
    `arm` writes its record under another name, puts the marker in the
    clipboard, and only then gives the record the name `capture` reads, so an
    `arm` that fails or is stopped part-way leaves no record. The
    arm record is deleted once a copied value has been read; the result of that
    delete is not checked. Without a fresh arm for the same bot it refuses
    before reading the clipboard, so an old token left there is not saved
    without `arm`. Arm one bot at a time: while two bots are armed together, a
    token copied for one can be captured under the other's name.
  - Before it reads an arm record, `capture` checks that `~/.thiscode` and the
    arm folder in it are real folders owned by the user, with owner-only
    permission bits (rwx------; the sticky and set-id bits are not looked at) and, on
    macOS, carry no ACL, and that the record is 0600. It only checks; it repairs
    nothing and refuses with `not-armed` before reading the clipboard. `arm` is
    what repairs the folders. When `~/.thiscode` or the arm folder was open
    before, `arm` locks the one that was open without making it 0700 yet (a
    `~/.thiscode` that already is 0700 is not touched), removes everything in
    the arm folder and checks that it is empty, and only then sets the arm
    folder and, last, `~/.thiscode` to 0700. If something cannot be removed it does not arm,
    tries to close the arm folder (mode 000), says whether that worked, and
    prints one line on how to move the folder away; until a later `arm` has
    emptied it, `capture` refuses. `install-gate.sh` repairs `~/.thiscode` as
    well; when it does so for a folder that was open, it closes the arm folder
    first, so the next `arm` empties it. Like the mode and ACL handling below, these
    checks go by `OSTYPE` and `uname`: with a changed `OSTYPE` or a different
    `uname` on PATH they are switched off, which takes someone who can already
    change the user's own environment.
  - The token protection above (the arm check, the folder checks and the ACL
    removal) covers the Discord token route
    (`scripts/discord-token-capture.sh`) only. The Slack token steps in
    `skills/slack-configure` do not have the arm check or the ACL removal yet.
- `scripts/patch-discord-bot-drop.sh` (the patch that lets one bot read
  another bot's messages in a server) now patches every copy of the Discord
  plugin it finds — the marketplaces copy and each version under `cache/`.
  Before, it stopped at the first copy, which left the cache copy — the one a
  running bot loads — unpatched while reporting "patched".
- Clipboard commands: macOS, WSL, Linux (Wayland, then xclip). Without one
  the script stops, and the user can run `paste <bot>`, a hidden prompt, in
  their own terminal instead. Its terminal check only guards against an
  accidental pipe; it is not a boundary against a program running as the same
  user. Exit 5 means saved, but the clipboard could not be emptied.
- `commands/start.md` and `commands/add-bot.md` use the same script instead
  of a heredoc. Reset Token is pressed once in its step,
  and the browser is not switched while the token is on screen.
- The bot folder is 0700 and `.env` 0600. On macOS the script also removes
  file ACLs from the folder, the temp file and `.env` and checks again — mode
  600 alone does not remove an inherited ACL that lets others read the file. If an ACL cannot be
  removed the script exits 3; a `.env` it has already written is then deleted,
  other keys in it included, and that delete is not checked. Whether the
  machine is macOS is taken from the shell's `OSTYPE`, and whether modes mean
  anything from `uname`, so a changed `OSTYPE` or a different `uname` on PATH
  switches this handling off. ACLs on Linux and Windows are not looked at.
- A failed attempt is recorded with a code from a fixed list of 13, such as
  `click-no-effect` (`install-gate.sh --reason-codes` prints the list; the
  same list is in `configs/install.yaml`). Free text is refused with exit 2
  and is not written.
- The install log `~/.thiscode/install-log.jsonl` is kept 0600 and its folder
  `~/.thiscode` 0700, whatever the umask. A symlink, a non-regular file,
  another owner or a second hard link is refused: `--attempted` exits 3, and
  `--handoff` and `--audit` do not read it. A folder set through
  `THISCODE_INSTALL_LOG` keeps its mode and is refused when group or others can
  write there. On macOS file ACLs on `~/.thiscode` and the log are removed as
  well. A hand-over at a human-only stop (or in manual mode) is still allowed
  when it cannot be recorded, so a person is not blocked by a log problem.
  A hand-over after three attempts, by contrast, is refused when the attempts
  cannot be recorded.
- `install-gate.sh` checks a gate name as a whole for `--handoff` and
  `--attempted`: letters, digits and underscores only, else exit 2.
- Four more places are handed over at once: the automation browser's permission
  window (`browser_permission_prompt`), the first trust prompt of a new work
  folder (`claude_workspace_trust_confirm`), Claude login (`claude_auth_login`)
  and restarting the session (`claude_session_restart`). bootstrap,
  install-hooks, meetings and self-update get `automation.yaml` tables too.
- The first trust prompt of a new work folder is answered by its label
  ("Yes, I trust this folder"), not by a line number.
- Unchanged: login, the human check (hCaptcha) and the token-reset
  confirmation stay human-only.
- What an installed bot must do differently now: try three times before
  handing a step over and say what was tried; ask before the terms box and
  before the three wider permissions; record a failure with a code, not a
  sentence; never ask for the token in chat.
- Not measured: the WSL clipboard branch on a real WSL machine (tests use
  stand-in commands).

---

## 2026-11-05 — ThisCode 1.4.2 browser auto-detect (ego lite → Aside → existing path)

- Before opening a website (create-bot portal step, help STEP 2.5, Slack app
  creation), the bot runs `node <plugin root>/scripts/browser-detect.mjs` once
  and uses the first browser that is installed and answers: ego lite → Aside →
  the existing path (a connected browser-automation tool, else the Playwright
  MCP install step). The user does not choose or configure a browser.
- The detector prints the CLI's absolute path, so it works on Macs where
  `~/.local/bin` is not on PATH. Every check has a time limit (15 s default),
  so a stuck CLI cannot stall setup.
- When ego lite is closed, its browser command opens the app window (measured
  on macOS).
- When ego lite stops for the user (a site permission prompt, a device
  chooser), the bot does not switch to the next browser: it tells the user
  what to click in the ego lite window (number button → the space marked
  "Need your action" → handle the prompt → "Return to agent") and resumes
  the same task space. It never clicks "Allow" on the user's behalf.
  (Measured on a macOS run: the old "on failure,
  next slot" line sent a permission-prompt stop to Aside.)
- Unchanged: the three human-only gates (login, hCaptcha, token-reset
  confirmation) and the copy-to-file path that keeps the bot token out of the
  model's view.
- What an installed bot must do differently now: check the detector's output
  before opening a site.
- Windows: PATH lookup only (not yet measured on Windows).

## 2026-09-05 — ThisCode 1.4.1 documentation and ownership clarifications

- Reconciled the Korean and English manuals: ThisCode's local installer scripts
  install the selected search tools; the km plugin's `/km:search` runs the
  fallback, while `/km:setup` configures storage, MCP integrations, and
  settings without installing GraphRAG or other search tiers.
- The current km fallback order is Tier 1 GraphRAG → Tier 2 Obsidian CLI →
  Tier 3 Obsidian MCP → Tier 4 text search.
  ThisCode's `vault-search MCP`
  installer provides a separate local tool; it is not a `/km:search` fallback
  tier. Older entries below keep the tier numbering they were written with.
- Documented the actual Codex export conditions: check mode is the default,
  and `--apply` reports an empty export only for the selected Codex layers
  outside the `repo` layer. The empty-export list remains a supported diagnostic
  result, not a removed command surface.
- Aligned public references on the `km` plugin id and marked the benchmark
  discussion as historical, with its 2026-05-13 result file as provenance.
- Kept archived local-tool benchmark IDs and figures explicitly historical while
  separating the current km order in setup, architecture, glossary, and
  chapter-mapping copy; README setup links now target the live setup heading.
- Matched the Korean README hook inventory to all seven registered hooks and
  generalized private deployment examples in the public Slack setup skills.
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
  publicly, so a fresh **legacy Tier-2** install always failed. (The historical
  ThisCode contract put the local embedding server in the third slot; this entry
  preserves its original numbering and does not describe the current km order.) Registration now uses
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
