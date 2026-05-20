# thiscode_agy — Antigravity Discord Bridge

> Drop-in Discord bridge for Antigravity (agy) CLI — Google Gemini-side companion to ThisCode (Claude Code) and ThisCodex (OpenAI Codex).

## 5-minute quickstart

### Prerequisites

- macOS (Linux mostly works, paths differ — see `setup-guide.md` §Linux)
- Python 3.10+
- tmux
- `agy` CLI installed (Antigravity CLI 1.0+) — typically `~/.local/bin/agy`
- A Discord application with bot token (see `setup-guide.md` §1 if you don't have one yet)
- A Discord guild you can add the bot to (Server Members + Message Content intents enabled in Developer Portal)

### Install

```bash
# 1. Create bot project directory
mkdir -p ~/my-agy-bot/scripts && cd ~/my-agy-bot

# 2. Copy templates from this skill
SKILL=~/.../ThisCode/skills/thiscode_agy
cp $SKILL/templates/launch.sh        ./launch.sh
cp $SKILL/templates/bridge.py        ./scripts/bridge.py
cp $SKILL/templates/discord_client.py ./scripts/discord_client.py
cp $SKILL/templates/agy_worker.py    ./scripts/agy_worker.py
cp $SKILL/templates/attachment.py    ./scripts/attachment.py
cp $SKILL/templates/conv_map.py      ./scripts/conv_map.py
cp $SKILL/templates/log_rotation.py  ./scripts/log_rotation.py
cp $SKILL/templates/discord_outbox.py ./scripts/discord_outbox.py
cp $SKILL/templates/persona-essence.md.template ./persona-essence.md

# 3. Python venv + dependencies
python3 -m venv .venv
.venv/bin/pip install 'discord.py>=2.3' websockets

# 4. Create Discord state dir + .env
BOT_NAME=mybot   # change to your bot's short name (used for tmux session + dir)
mkdir -p ~/.claude/channels/discord-$BOT_NAME
cp $SKILL/templates/env.template ~/.claude/channels/discord-$BOT_NAME/.env
chmod 600 ~/.claude/channels/discord-$BOT_NAME/.env
# Edit ~/.claude/channels/discord-$BOT_NAME/.env:
#   DISCORD_BOT_TOKEN=<your bot token from Discord Developer Portal>
#   AGY_PATH=/Users/<you>/.local/bin/agy
#   AGY_UNSAFE=0   # set to 1 only on trusted single-user host

# 5. Edit persona-essence.md with your bot's persona (35-line max recommended)

# 6. Launch
BOT_NAME=mybot bash launch.sh
# Should open tmux session 'mybot' with 2 panes: top=bridge log, bottom=agy TUI

# 7. (Recommended) Add zsh alias
echo "alias mybot='cd ~/my-agy-bot && BOT_NAME=mybot bash launch.sh'" >> ~/.zshrc
```

### Smoke test

In your Discord guild, mention the bot: `@<your-bot> hi`. Within a few seconds:
- bridge daemon pane (top) shows `[RAW]` then `[INBOX]` line
- agy TUI pane (bottom) shows the message typed in (visual feedback via `tmux send-keys`)
- Discord channel receives bot reply

If nothing happens, see `references/troubleshooting.md` — the most common cause is **OAuth scope mismatch** (bot needs `bot` scope, not just `applications.commands`).

## Architecture (one paragraph)

`bridge.py` runs an async daemon that polls a Discord WebSocket gateway via `discord.py`. Each `@mention` lands in `_handle_message` → dedup check → `BridgeMessage` → `asyncio.Queue` → `_worker` → `_dispatch`. The dispatcher composes `persona + content`, spawns `agy --print` via `AgyWorker.run_y3` (argv-based, `shell=False`, sandboxed by default), and replies via `DiscordReplyAdapter` (using `message.reply()` for proper thread context). For asset-generation tasks (`/agy-asset` prefix), it uses `Y-2 PTY` (`agy --prompt-interactive`) and watches for new files in `assets/<conv>/`.

For visual UX, each inbound message is also `tmux send-keys`-injected into the agy TUI pane (HS_AGY_PANE env). This is decorative — the actual response comes from the Y-3 subprocess. Mirrors the sshee/Codex bridge pattern.

## Files in this skill

```
thiscode_agy/
├── SKILL.md                     # frontmatter + triggers (use Skill tool to load)
├── README.md                    # ← you are here (quickstart)
├── setup-guide.md               # detailed Discord OAuth + agy install walkthrough
├── templates/
│   ├── launch.sh                # 2-step tmux launch + wrapper suicide guard
│   ├── bridge.py                # async bridge daemon (inbox poll + Discord gateway)
│   ├── discord_client.py        # discord.py gateway client + reply adapter + dedup
│   ├── agy_worker.py            # agy CLI subprocess + Y-2 PTY session
│   ├── attachment.py            # path-traversal-safe attachment sandbox
│   ├── conv_map.py              # per-channel agy conversation_id mapping
│   ├── log_rotation.py          # daily log rotation (mode 700)
│   ├── discord_outbox.py        # outbox polling discord adapter (smoke test mode)
│   ├── persona-essence.md.template
│   └── env.template
└── references/
    ├── architecture.md          # Y-3 vs Y-2 hybrid, why this design
    └── troubleshooting.md       # OAuth scope, intents, tmux pane, persona prepend
```

## Related ThisCode skills

- `thiscodex/` — same pattern for OpenAI Codex CLI
- `knowledge-manager/` — vault ingest pipeline (Karpathy/Orchestrator Pattern)
- `prompt/` — prompt engineering library

## License & attribution

MIT (same as ThisCode). Extracted from a production bot (`agent-hassabis/`) running Demis Hassabis persona on the maintainer's vault. Persona-specific content stripped — supply your own in `persona-essence.md`.
