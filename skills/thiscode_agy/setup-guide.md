# setup-guide.md — thiscode_agy

Full walkthrough for a fresh Discord + Antigravity bot setup.

---

## §1. Create the Discord bot (Developer Portal)

1. Open https://discord.com/developers/applications
2. **"New Application"** → name (example: `<your-bot-name>`)
3. Left sidebar → **Bot** tab:
   - **Reset Token** → copy and save securely (you'll paste into `.env`)
   - Scroll to **Privileged Gateway Intents**:
     - ✅ **MESSAGE CONTENT INTENT** — REQUIRED (without this, your bot sees mentions but no message content)
     - ✅ **SERVER MEMBERS INTENT** — optional but recommended (member name lookups)
     - PRESENCE INTENT — leave off unless you need it
4. Left sidebar → **OAuth2** → **URL Generator**:
   - **Scopes (CRITICAL — must include `bot`)**:
     - ✅ `bot`
     - ✅ `applications.commands` (optional, for future slash command support)
   - **Bot Permissions** (minimal set):
     - ✅ View Channels (1024)
     - ✅ Send Messages (2048)
     - ✅ Read Message History (65536)
     - ✅ Embed Links (16384)
     - ✅ Attach Files (32768)
     - ✅ Add Reactions (64)
     - Sum = 117824 (or use the Discord UI checkboxes — it computes the integer for you)

   Or hand-construct the URL directly:
   ```
   https://discord.com/api/oauth2/authorize?client_id=<your-app-id>&permissions=117824&scope=bot+applications.commands
   ```
5. Copy the **Generated URL** at the bottom → open in browser → select your guild → **Authorize**.

> ⚠️ **CRITICAL — common gotcha**: if you only add `applications.commands` scope (no `bot`), your bot WILL appear in `/users/@me/guilds` but every `GET /channels/.../messages` returns `{"code": 50001, "message": "Missing Access"}` and `on_message` never fires. You'll see only heartbeat logs. **Always include `bot` scope.** (See `references/troubleshooting.md` §1 for diagnosis.)

## §2. Install `agy` (Antigravity CLI)

Visit https://antigravity.google.com/ to get the CLI installer (closed-beta as of 2026-05). After install:

```bash
which agy
# Expected: /Users/<you>/.local/bin/agy
agy --version
# Expected: 1.0.0 (or later)
```

If installed elsewhere, set `AGY_PATH` in `.env`.

## §3. Python environment

Requires Python 3.10+ (3.14 tested):

```bash
cd ~/my-agy-bot
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
# (Or explicitly: .venv/bin/pip install 'discord.py>=2.3' pytest pytest-asyncio)
```

> ⚠️ If installing without `requirements.txt`, `'discord.py>=2.3'` must be quoted in zsh (otherwise `>=` is interpreted as redirect).
>
> Note: `websockets` package is NOT required for the agy bridge (it's only needed for the codex bridge which uses JSON-RPC over WebSocket).

## §4. tmux setup

The launch script creates a 2-pane tmux session:
- **Top pane**: bridge daemon (Python) — shows `[RAW]`, `[INBOX]`, `[OUTBOX]`, heartbeat
- **Bottom pane**: `agy --dangerously-skip-permissions` TUI — shows messages visually injected from bridge

tmux config requirements:
- `tmux` 3.0+ (uses `split-window -P` to capture pane id)
- Any `base-index` / `base-pane-index` setting works (script auto-detects via `split-window -P -F`)

## §5. Create channel state directory

```bash
BOT_NAME=mybot   # short single-token name; tmux session + path use this
mkdir -p ~/.claude/channels/discord-$BOT_NAME
chmod 700 ~/.claude/channels/discord-$BOT_NAME
```

This dir holds:
- `.env` — bot token + agy path
- `bot-info.json` — written by bridge on Discord gateway READY (user_id, name, ready_at)
- `inbox/` — optional inbox polling mode files (gateway mode uses queue directly)
- `outbox/` — written by smoke test mode
- `soul.md` — optional, full persona (auto-loaded by some agents)

## §6. Fill in `.env`

Copy template:

```bash
cp <ThisCode>/skills/thiscode_agy/templates/env.template \
   ~/.claude/channels/discord-$BOT_NAME/.env
chmod 600 ~/.claude/channels/discord-$BOT_NAME/.env
```

Edit:

```
DISCORD_BOT_TOKEN=<paste token from Developer Portal §1>
AGY_PATH=/Users/<you>/.local/bin/agy
AGY_UNSAFE=0
# AGY_UNSAFE=1 only on a single-user trusted host —
# this passes --dangerously-skip-permissions to agy (no confirm prompts).
# GEMINI_MODEL=<optional — default is whatever agy picks at startup>
```

## §7. Compose `persona-essence.md`

This is the 35-line max persona snippet prepended to every Y-3 prompt (because `agy --print` does NOT auto-load `GEMINI.md`). Keep it tight — first-person ID, voice, key principles. See `templates/persona-essence.md.template` for shape.

## §8. First launch

```bash
cd ~/my-agy-bot
BOT_NAME=mybot bash launch.sh
```

Expected output:

```
[INFO] tmux 'mybot' 생성 — 2-step: placeholder → split → env 확정 후 bridge 시작
[INFO] agy TUI pane = mybot:1.2 · bridge daemon pane = mybot:1.1
[INFO] BOT_NAME=mybot
[INFO] WD=/Users/<you>/my-agy-bot
[INFO] DISCORD_STATE_DIR=/Users/<you>/.claude/channels/discord-mybot
[agy-bridge] start (Discord gateway) — channel=discord-mybot agy=/Users/<you>/.local/bin/agy
[HH:MM:SS] gateway READY — <bot-name>#1234 (user_id=...)
[HH:MM:SS+30] mybot alive — queue=0 channels=0
```

If the second pane shows the agy TUI banner with `>` prompt — you're good.

To attach later: `tmux attach -t mybot` (Ctrl+B,D to detach, keeps running).

## §9. Smoke test

In your guild, send `@<your-bot> hello` in any channel the bot can see. Within a few seconds:

- Top pane logs `[RAW] ch=<id> ... mentioned=True content='...hello...'`
- Top pane logs `[INBOX] ch=<id> ...` and `[OUTBOX] ch=<id> reply_len=...`
- Bottom (agy) pane shows `[Discord] hello` typed at the prompt (then `[reply] ...` after response)
- Discord channel receives the bot's reply (threaded under your message)

If you don't see `[RAW]`, the bot isn't receiving messages — almost always OAuth scope (`bot` missing) or Message Content Intent disabled in Developer Portal. See `references/troubleshooting.md`.

## §10. Optional: zsh alias

```bash
echo "alias mybot='cd ~/my-agy-bot && BOT_NAME=mybot bash launch.sh'" >> ~/.zshrc
echo "alias mybot-attach='tmux attach -t mybot'" >> ~/.zshrc
source ~/.zshrc
```

Now `mybot` from anywhere boots the bot. `mybot-attach` re-attaches to the running session.

The launch script has a **suicide guard**: running `mybot` from INSIDE the `mybot` tmux session is refused (would otherwise kill its own session). Detach first.

## §11. Daily ops

- **Stop**: `tmux kill-session -t mybot` (also kills agy CLI)
- **Restart**: `BOT_NAME=mybot bash launch.sh` (wrapper auto-cleans old session)
- **Logs**: `~/my-agy-bot/state/logs/YYYY-MM-DD/bridge.log` (daily rotated, mode 700)
- **Dedup state**: `~/my-agy-bot/state/dedup.json` (TTL 24h, max 5000 entries)
- **Conversation map**: `~/my-agy-bot/state/conversations/map.json` (channel_id → agy conv_id)

## §12. Security notes

- `.env` is `chmod 600`. State root `mkdir mode 0o700`. Attachment sandbox checks for path traversal.
- `agy_worker.py` builds argv as a list (not shell string) → no command injection.
- `--sandbox` is default; `AGY_UNSAFE=1` only when you trust the host single-user.
- Tokens: rotate via Discord Developer Portal → Bot → Reset Token if leaked.
- Logs may contain message content — they're mode 700, but back up carefully.
