---
name: thiscode_agy
description: Use when integrating Antigravity (agy) CLI with Discord — Y-3 single-shot + Y-2 PTY interactive bridge daemon, tmux 2-pane visual layout (daemon log + agy TUI), per-channel conversation isolation, persona prepend, attachment sandbox, dedup, atomic dispatch with per-channel flock. Drop-in mirror of the Claude Code bridge pattern (AgyDiscordBot + DiscordReplyAdapter + AgyWorker) for Gemini/Antigravity-side bots.
version: 1.0.0
created: 2026-05-21
triggers:
  - "agy Discord 봇 만들고 싶다"
  - "Antigravity CLI 를 Discord 에 연결"
  - "Y-3 단발 + Y-2 인터랙티브 bridge"
  - "Gemini bridge 봇"
  - "/thiscode-agy" slash command
---

# thiscode_agy — Antigravity Discord Bridge Skill

> **Why this exists**: ThisCode/ThisCodex 가 Claude Code (Anthropic) + Codex (OpenAI) bridge 를 표준화했지만, **Antigravity CLI (Google Gemini)** 도 같은 패턴으로 Discord 에 묶을 가치가 있다. 본 스킬은 그 reference implementation 의 templated 버전이다.

## What this skill provides

**Architecture (Y-3 + Y-2 hybrid)**:
- **Y-3 (default)**: `agy --print` subprocess per Discord message. Reliable, deterministic stdout for Discord reply.
- **Y-2 (asset mode)**: `agy --prompt-interactive` PTY session for `/agy-asset` commands (image/file generation).
- **tmux 2-pane visual**: top = bridge daemon log (live `[RAW]`/`[INBOX]`/`[OUTBOX]` events), bottom = agy CLI TUI (Discord message visually injected via `tmux send-keys` — UX mirror of sshee codex pattern).

**Components (genericized from agent-hassabis/)**:
- `templates/launch.sh` — 2-step tmux launch (placeholder → split → env-correct bridge start), wrapper with suicide guard
- `templates/bridge.py` — async bridge daemon (inbox polling fallback + Discord gateway live), per-channel `flock`, tmux send-keys visual inject
- `templates/discord_client.py` — `AgyDiscordBot` + `DiscordReplyAdapter` + `DedupStore` + per-channel `asyncio.Lock`, heartbeat task, raw debug print
- `templates/agy_worker.py` — agy CLI subprocess invocation (argv-based, `shell=False`, clean env), conversation_id extraction
- `templates/attachment.py`, `conv_map.py`, `log_rotation.py`, `discord_outbox.py` — supporting utilities
- `templates/setup_bot_dirs.sh` — state + channel dir bootstrap (mode 700, umask 077)
- `templates/requirements.txt`, `.gitignore` — Python deps + git hygiene
- `templates/persona-essence.md.template` — persona prepend (only true template file; copy + edit)
- `templates/env.template` — `.env` shape (`DISCORD_BOT_TOKEN`, `AGY_PATH`, `AGY_UNSAFE`, optional `GEMINI_MODEL`)

**Documentation**:
- `README.md` — 5-minute quickstart
- `setup-guide.md` — full setup walkthrough (Discord Developer Portal OAuth + Python venv + agy CLI install + tmux layout)
- `references/architecture.md` — Y-3 vs Y-2 design, why this hybrid, attachment sandbox model
- `references/troubleshooting.md` — common issues (OAuth scope, message_content intent, tmux pane numbering, persona prepend)

## When to use this skill

- Setting up a new Antigravity-based Discord bot
- Mirroring the sshee/Codex or agy bridge pattern for a different AI CLI
- Diagnosing existing agy bridge issues (jump to `references/troubleshooting.md`)
- Adding `/agy-asset` (Y-2 PTY) capability to an existing bot

## Quick start

See `README.md` for the full quickstart (copy commands for each file into `~/my-agy-bot/{launch.sh,persona-essence.md,requirements.txt,.gitignore}` and `~/my-agy-bot/scripts/{bridge.py,discord_client.py,agy_worker.py,attachment.py,conv_map.py,log_rotation.py,discord_outbox.py,setup_bot_dirs.sh}`). Most templates have their final filename — only `env.template` and `persona-essence.md.template` use the `.template` suffix and require a rename on copy.

See `setup-guide.md` for full details including OAuth permissions (CRITICAL — `bot` scope required, not just `applications.commands`).

## Conventions

- **Bot name = single token** (no spaces). Used for tmux session name + Discord channel state dir name.
- **Channel state dir = `~/.claude/channels/discord-<bot-name>/`** — contains `.env`, `bot-info.json`, `inbox/`, `outbox/`, `soul.md`.
- **WD = bot project dir** — `launch.sh`, `bridge.py`, `discord_client.py`, `agy_worker.py`, `persona-essence.md`, `state/`.
- **agy CLI permissions**:
  - default = `--sandbox` (prompt for sensitive ops)
  - `AGY_UNSAFE=1` in .env = `--dangerously-skip-permissions` (no prompts; only when single-user trusted host)

## What this skill does NOT do

- It does NOT install `agy` CLI itself. Get it from Antigravity website + place at `~/.local/bin/agy` (default) or set `AGY_PATH` env.
- It does NOT manage Discord bot creation (Developer Portal step) — see `setup-guide.md` §1 for that walkthrough.
- It does NOT handle multi-bot orchestration (use ThisCode roster system for that).

## Reference: the production bot this skill was extracted from

`agent-hassabis/` in the maintainer's vault — Demis Hassabis persona, alias `hs`, tmux session `hs`, channel `~/.claude/channels/discord-hs/`. The persona-specific content was stripped to make this skill generic.
