# references/architecture.md

## Why Y-3 + Y-2 hybrid

### Y-3 (`agy --print` single-shot subprocess)
- **Reliable stdout** — agy emits the response on stdout, exits with rc=0/!=0. Easy to capture and forward to Discord.
- **Deterministic** — each Discord message spawns a fresh subprocess. No state leakage across messages.
- **Persona injection via `--add-dir`** — agy auto-loads `GEMINI.md`/`AGENTS.md` from CWD only in interactive mode, NOT print mode. So the bridge prepends `persona-essence.md` content to the user prompt manually.
- **conversation_id continuity** — `--conversation <uuid>` keeps the same agy conversation across spawns. The bridge maps `chat_id → conv_id` via `conv_map.ConvMap`, persisted in `state/conversations/map.json`.
- **Per-channel cwd** — each Discord channel gets its own `state/channels/<safe-ch-id>/cwd/`. This isolates agy's working directory (e.g. file operations stay channel-scoped).
- **Trade-off**: token cost is higher (persona reloaded each time). For a casual chat bot this is fine; for high-volume use, switch to Y-2.

### Y-2 (`agy --prompt-interactive` PTY session)
- **Used for `/agy-asset` commands** — asset generation (image, file output) benefits from a persistent agy session that can iterate.
- **PTY required** — agy's interactive mode wants a TTY. The bridge uses Python's `pty.openpty()` and feeds prompts via the master fd.
- **Output capture heuristic** — `AgyPTYSession.send` writes prompt + newline, then drains the master fd until 500ms of silence (assumed = response complete). Brittle but works for typical responses.
- **`add_dirs`** — passed once at session start; subsequent `send()` calls inherit.
- **Cleanup** — `session.close()` sends SIGTERM, waits 5s, falls back to SIGKILL.

### Why both, not just one
- Y-3 is the workhorse — 95% of conversational use.
- Y-2 is only when state continuity inside agy itself matters (file I/O across turns, image iteration).
- Keeping them separate avoids the brittle "parse a PTY scrollback" problem for normal chats.

## Persona prepend (why GEMINI.md doesn't auto-load in print mode)

Empirically confirmed (2026-05 with agy 1.0):
- `agy --prompt-interactive` (TUI mode) → auto-loads `GEMINI.md`, `AGENTS.md` from CWD
- `agy --print` (single-shot) → does NOT auto-load these (or hangs silently if they cause a privileged-op prompt)

Workaround: `bridge._dispatch` builds `full_prompt = persona + "\n\n---\n\n" + user_content`. Persona stays small (35 lines max recommended) to keep token overhead reasonable.

Reference incident: "Phase 3 Hassabis bridge" decision log — `agy --print --add-dir <vault>` hung for 5+ test runs trying to auto-load GEMINI.md. Stripping the auto-load assumption + manual prepend fixed it.

## Attachment sandbox

`AttachmentSandbox.store()` writes to `state/attachments/<guild>/<channel>/<message>/<filename>`:
- `filename` is path-traversal-stripped (no `..`, no leading `/`, alnum-only fallback)
- Each message gets its own dir to avoid collision
- Bridge passes `add_dirs=[stored.parent]` to agy so the file is reachable

## per-channel flock (race protection)

`bridge.process_one()` acquires an exclusive `fcntl.flock` on `state/conversations/<safe-ch>.lock` before dispatch. This ensures a channel's messages are processed in order even if multiple inbox files arrive (or in the gateway mode, even if dedup somehow races).

In gateway mode, `AgyDiscordBot._worker` ALSO acquires a per-channel `asyncio.Lock` (`_channel_locks`) — the flock is for cross-process safety, the asyncio lock is for in-process queue serialization. Both layers because the gateway code reuses `bridge._dispatch` which expects flock semantics.

## Visual feedback (tmux send-keys → agy TUI pane)

The bottom tmux pane runs `agy --dangerously-skip-permissions` interactively (not driven by the bridge — purely decorative). `bridge._tmux_inject()` sends `C-u` (clear line) then `-l <text>` (literal, no Enter) to the pane so the user sees the Discord message appear at the prompt without agy actually processing it (the real processing is the Y-3 subprocess).

`HS_AGY_PANE` env var carries the tmux target (e.g. `mybot:1.2`). `launch.sh` captures it from `tmux split-window -P -F '...'` after the split. The 2-step launch (placeholder bash → split → send-keys to start bridge with correct env) ensures the env value is right even on hosts with non-default `base-pane-index`.

## Heartbeat

`AgyDiscordBot._heartbeat_loop` prints `[HH:MM:SS] <bot> alive — queue=N channels=N` every 30s to the daemon pane. Provides liveness proof without needing to attach. `channels` = count of `_channel_locks` keys, which is populated lazily on first message per channel.

If you see heartbeat ticking but `queue=0` AND `channels=0` for minutes despite known mentions, the bot is connected to Discord gateway but not receiving messages — almost always OAuth scope (see `troubleshooting.md` §1).

## File layout

```
~/my-agy-bot/
├── .venv/                          # Python venv
├── launch.sh                       # 2-step tmux launch + suicide guard
├── persona-essence.md              # ~35 lines, prepended to every Y-3 prompt
├── scripts/
│   ├── bridge.py                   # async daemon
│   ├── discord_client.py           # AgyDiscordBot + DiscordReplyAdapter + DedupStore
│   ├── agy_worker.py               # AgyWorker (Y-3 subprocess + Y-2 PTY)
│   ├── attachment.py               # AttachmentSandbox
│   ├── conv_map.py                 # ConvMap (chat_id → agy conv_id)
│   ├── log_rotation.py             # RotatingLog (daily, mode 700)
│   └── discord_outbox.py           # OutboxDiscord (smoke test mode)
└── state/                          # mode 700, all per-bot persistent state
    ├── conversations/
    │   ├── map.json                # chat_id → conv_id map
    │   └── <safe-ch>.lock          # per-channel flock
    ├── attachments/<guild>/<ch>/<msg>/<file>
    ├── assets/<conv>/              # Y-2 mode asset outputs
    ├── dedup.json                  # message_id dedup (TTL 24h)
    └── logs/YYYY-MM-DD/bridge.log  # daily rotated

~/.claude/channels/discord-<bot>/
├── .env                            # mode 600 — DISCORD_BOT_TOKEN, AGY_PATH, AGY_UNSAFE
├── bot-info.json                   # mode 600 — user_id, name, ready_at (written by bridge on READY)
├── soul.md                         # optional — full persona doc (35-line essence is in persona-essence.md)
├── inbox/                          # optional — inbox polling mode files
└── outbox/                         # smoke test outputs
```
