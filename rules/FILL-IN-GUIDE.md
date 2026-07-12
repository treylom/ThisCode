# Fill-in Guide — make the bundled rules actually fire

Every `rules/<topic>.md` ships as a generic skeleton ending in a `▶ Fill in:`
line. **A blank fill-in does not error — the rule silently never applies.**
(Example: if no completion thread id is filled in, the completion-report gate
simply stays off and nobody notices.) Walk this checklist once per
bot/workspace; ~15 minutes. The §0 guided onboarding
([docs/SETUP-CONFIG-GUIDE.md](../docs/SETUP-CONFIG-GUIDE.md)) can do this
interview for you — this file is the manual path and the reference for what
"filled" looks like.

How to fill: edit the rule file in your bot's `rules/` copy and replace the
`▶ Fill in:` line with a short concrete block (keep it under ~5 lines; these
files stay lean by design).

## Checklist (12 items, grouped by file)

### discord-comms.md — reply tool · bot ids · completion thread · channel map
- **Where to get it**: reply tool name = your Discord integration's tool id
  (Claude Code official plugin: `mcp__plugin_discord_discord__reply`). Bot
  user_ids = Discord Developer Portal → your app → "Copy User ID", or your
  `bot-roster.yaml`. Completion thread = create one thread in your server and
  paste its id (right-click → Copy ID, with Developer Mode on).
- **Filled example**:
  ```
  Reply tool: mcp__plugin_discord_discord__reply
  Roster SoT: ~/workspace/bot-roster.yaml (research=1111…, writing=2222…)
  Completion thread: 3333… · Meetings: #ops-meetings · Main: #general
  ```
- **If blank**: bots can't @mention each other reliably; completion gate off.

### autonomy.md — completion thread id · authority boundaries · heartbeat
- **Where to get it**: same completion thread id as above. Authority
  boundaries = which actions this bot may take alone vs. must ask (start from:
  read/draft = free, commit/edit = self-judge, deploy/public-repo = ask).
- **Filled example**:
  ```
  Completion thread: 3333…
  Authority: read/search/draft free · repo commits self-judge · pushes ask
  Heartbeat: bridge progress heartbeat 180s (ThisCodex bot.py) — keep ON
  ```
- **If blank**: the bot either over-asks or finishes work without reporting.

### meeting-protocol.md — meeting filename · progress path · cadence
- **Filled example**:
  ```
  Meetings live in: <vault>/meetings/<date>-<topic>/ (00-context…03-outcome)
  Progress file: 02-progress.md — append "[KST] <bot> | <state> | <1 line>"
  Liveness cadence: every ≤3 min during active meetings
  ```
- **If blank**: multi-bot meetings happen in raw chat with no shared record.

### orchestration.md — bot identity derivation · identity guard · reviewers
- **Where to get it**: identity = how your launcher names bots (with this
  bundle: `DISCORD_STATE_DIR` basename minus `discord-`, or `CODEX_BOT`).
  Set `ORCHESTRATOR_BOT=<name>` in the orchestrator's env so the
  `dispatch-verify` hook arms itself.
- **Filled example**:
  ```
  <bot> = basename($DISCORD_STATE_DIR) minus "discord-"; ORCHESTRATOR_BOT=lead
  Identity guard: soul.md injected at SessionStart is the only identity SoT
  Review chain: worker output → second bot review → human sign-off
  ```
- **If blank**: dispatch-verify hook never arms; identity mixups go uncaught.

### voice.md — persona markers · signature
- **Where to get it**: your bot's `soul.md` (the persona file is the SoT —
  this rule just mirrors its self-check lines).
- **Filled example**: `Signature: "— Atlas" on every report; plain-language
  rule: explain jargon on first use when talking to the owner.`
- **If blank**: persona drifts; no per-response self-check.

### source-fact.md — roster/SoT paths · token-optimizer raw bypass
- **Filled example**:
  ```
  Roster SoT: ~/workspace/bot-roster.yaml · channels dir: ~/.claude/channels/
  Raw bypass: not using a token-optimizer proxy — N/A
  ```
- **If blank**: bots assert names/ids from memory instead of checking a file.

### skill-process.md — skill system · debugging skill
- **Filled example**: `Skill system: Claude Code Skill tool (superpowers
  plugin); debugging = superpowers:systematic-debugging before any fix.`
- **If blank**: skills exist but nothing tells the bot to invoke them first.

### knowledge-retrieval.md (×2 fill-ins) — KB tools · memory search · split
- **Filled example**:
  ```
  KB: vault-search MCP (semantic) → obsidian-cli (exact) → ripgrep (fallback)
  Memory search: grep SHARED-INDEX.md first, then fetch the linked entry
  Split: shared (cross-bot facts) vs per-bot WD memory (persona quirks)
  ```
- **If blank**: every lookup falls through to raw grep; shared memory unused.

### porting-infra.md — companion repos · secret scan
- **Filled example**:
  ```
  Sync targets: ThisCode + ThisCodex (push both when rules change)
  Secret scan before push: grep -rn "ntn_[a-zA-Z0-9]" --include="*.md" . ;
  smoke test must be green first
  ```
- **If blank**: rule changes drift between repos; secrets ride along in pushes.

### image-ops.md — image toolchain · reference assets
- **Filled example**:
  ```
  Edit-capable model: gpt-image-2 via $imagegen (image-input mode)
  Deterministic overlay tool: PIL/ImageMagick (technical images only)
  Reference assets: assets/refs/ (person/brand/product ground truth)
  ```
- **If blank**: bots route edits to generators (composition drift) or invent real people/brand looks.

## Verify you're done

```bash
grep -rn "▶ Fill in:" rules/   # ideally returns nothing in YOUR bot's copy
```

Keep the upstream repo copies generic (placeholders intact); only your
deployed bot-WD copies get filled values.
