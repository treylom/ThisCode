# references/troubleshooting.md

Common issues + fixes. Most are first-launch papercuts.

---

## §1. Bot connects to gateway but never receives messages (heartbeat ticks, `queue=0 channels=0` forever)

**Symptom**: bridge daemon pane shows `[HH:MM:SS] gateway READY — <bot>#1234` then every 30s `<bot> alive — queue=0 channels=0`. You `@<bot>` in Discord but no `[RAW]` log line appears.

**Most likely root cause**: OAuth scope mismatch — bot was authorized with only `applications.commands` scope (no `bot` scope). The bot APPEARS in `/users/@me/guilds` but every channel access returns `Missing Access (50001)`, and `on_message` never fires.

**Diagnosis** (REST API, no Python needed):

```bash
TOK="$(grep '^DISCORD_BOT_TOKEN=' ~/.claude/channels/discord-<bot>/.env | cut -d= -f2 | tr -d '"')"

# What guilds does the bot see?
curl -s -H "Authorization: Bot $TOK" "https://discord.com/api/v10/users/@me/guilds"
# Expected: at least one guild with your bot's permissions integer.

# Can the bot read messages from the target channel?
curl -s -H "Authorization: Bot $TOK" \
  "https://discord.com/api/v10/channels/<channel-id>/messages?limit=1"
# Expected: a JSON array of messages.
# If you get {"message": "Missing Access", "code": 50001} → OAuth scope problem.

# What scopes did the default install URL use?
curl -s -H "Authorization: Bot $TOK" "https://discord.com/api/v10/applications/@me" \
  | python3 -c "import sys, json; print(json.load(sys.stdin).get('install_params'))"
# If scopes is ['applications.commands'] only (no 'bot') → re-OAuth with bot scope.
```

**Fix**: Re-authorize the bot with `bot` scope. Generate URL via Discord Developer Portal → OAuth2 → URL Generator, or hand-construct:

```
https://discord.com/api/oauth2/authorize?client_id=<app-id>&permissions=117824&scope=bot+applications.commands
```

`permissions=117824` = View Channels + Send Messages + Embed Links + Attach Files + Read Message History + Add Reactions (minimum for a chat bot). Open in browser → select target guild → Authorize.

After re-OAuth, the bridge daemon auto-detects new permissions on the next inbound message — no restart needed. First mention should immediately show `[RAW]` + `[INBOX]` + Discord reply.

## §2. Bot receives mentions but `msg.content` is empty (`content='...'` empty in `[RAW]` line)

**Symptom**: `[RAW]` line shows the message arrived, mentioned=True, but content is empty or just contains the mention `<@...>`.

**Root cause**: **Message Content Intent** is not enabled in Discord Developer Portal → Bot → Privileged Gateway Intents. Without it, Discord strips message content from gateway events for non-mentioned-bots messages (and reduces what mentioned-bots see).

**Fix**: Open https://discord.com/developers/applications/<app-id>/bot → scroll to **Privileged Gateway Intents** → toggle **MESSAGE CONTENT INTENT** ON → Save. No bot restart needed (Discord re-handshakes on next reconnect, or restart for immediate effect).

## §3. agy `--print` hangs forever, never returns

**Symptom**: bridge logs `_dispatch chat=...` then nothing — eventually hits `agy timeout after 300s` exception.

**Likely cause**: agy is waiting for a confirmation prompt (file write, network access) but you're in `--sandbox` mode and stdout is a pipe (no TTY for user input).

**Diagnoses**:
- Look at agy stderr in the bridge log — there should be a "permission denied" or "approve?" line.
- Check `AGY_UNSAFE` env: if `0`, agy is in sandbox mode → it WILL prompt for sensitive ops.

**Fix options**:
- Set `AGY_UNSAFE=1` in `.env` (only on trusted single-user host) → agy uses `--dangerously-skip-permissions`, no prompts.
- Or constrain prompts to non-sensitive ops only (no file writes, no network, no shell).
- Or pre-stage files in `--add-dir` directories that agy already has access to.

## §4. tmux panes don't show what you expect (`HS_AGY_PANE` mismatch)

**Symptom**: bridge logs `[tmux-inject] failed: ...` OR Discord messages don't appear visually in the agy pane.

**Root cause**: tmux pane numbering varies by config (`base-index`, `base-pane-index`). The launch script uses `tmux split-window -P -F '#{session_name}:#{window_index}.#{pane_index}'` to capture the actual pane id, then passes it as `HS_AGY_PANE` env to the bridge.

**Diagnosis**:
```bash
tmux list-panes -t <bot>
# Look at the pane indexes (1 and 2 typically)
echo $HS_AGY_PANE   # in the bridge pane
# Should match the agy pane's full target like "<bot>:1.2"
```

**Fix**: Re-launch (`tmux kill-session -t <bot>` then `BOT_NAME=<bot> bash launch.sh`). The 2-step launch is the fix — if you're seeing this on an old launch.sh, ensure the latest template is in use.

## §5. Wrapper kills the session you're in (`bash: tmux: kill-session ...`)

**Symptom**: You're attached to `<bot>` tmux, you type `<bot>` alias from within → terminal closes / session dies.

**Root cause**: Old launch.sh wrapper unconditionally `tmux kill-session -t <bot>` before recreating. From inside the session, this kills your own session.

**Fix**: Templates ≥2026-05-21 include a **suicide guard**. Inside the wrapper:

```bash
if [[ -n "${TMUX:-}" ]] && tmux display-message -p "#S" | grep -qx "<bot>"; then
  echo "[WARN] 이미 '<bot>' tmux 안 — wrapper 자살 가드 발동"
  exit 0
fi
```

If you see this on an old template, copy the latest `launch.sh` from `templates/`.

## §6. Discord reply `text.length undefined` error (MCP plugin variant)

**Symptom**: bridge.py logs `[discord-worker] ERROR ...: text.length undefined`.

**Root cause**: Some Discord plugin/SDK paths choke on `None` or empty `text` arguments to `reply()`.

**Fix**: The current `bridge._dispatch` already guards with `reply_text = result.stdout or f"(empty agy response, exit={result.exit_code})"`. If you see this error in your fork, check for any custom reply paths that bypass the guard.

## §7. `discord.py>=2.3` install fails in zsh

**Symptom**: `pip install discord.py>=2.3` → zsh: bad pattern: ... OR redirects to a file named `=2.3`.

**Root cause**: zsh interprets `>=` as a redirect glob.

**Fix**: Quote the version specifier:
```bash
.venv/bin/pip install 'discord.py>=2.3'
```

## §8. agy CLI not found (`[FATAL] agy CLI 없음`)

**Symptom**: launch.sh exits with `[FATAL] agy CLI 없음 (/Users/<you>/.local/bin/agy)`.

**Diagnosis**:
```bash
which agy
ls -la $HOME/.local/bin/agy
agy --version
```

**Fix**: Install agy CLI per Antigravity website. If installed elsewhere (e.g. `/usr/local/bin/agy`), set `AGY_PATH=/usr/local/bin/agy` in `.env`.

## §9. Bot reply is the literal `(empty agy response, exit=0)` string

**Symptom**: Discord receives this literal string instead of an actual response.

**Root cause**: agy ran successfully (exit 0) but printed nothing to stdout. Usually means agy hit an internal error or the prompt was empty.

**Diagnoses**:
- Check `[INBOX]` line for `content=...` — was the user message empty?
- Run `agy --print "<the prompt>" --sandbox` manually from CWD `~/my-agy-bot/state/channels/<safe-ch>/cwd/` and see what it prints.

## §10. Bridge daemon silently dies (`tmux ls` shows session, but pane is dead)

**Symptom**: Heartbeat stops appearing in bridge pane but tmux session still listed.

**Diagnosis**:
```bash
ps aux | grep "bridge.py\|agy"
# Both bridge.py and agy CLI should be running.

tmux capture-pane -t <bot>:1.1 -p -S -200 | tail -30
# Look for Python traceback in scrollback.
```

**Fix**: Restart the session. If the crash repeats, capture the traceback and file an issue. Most common cause is an unhandled exception in `_dispatch` → `_worker` doesn't restart (a known limitation of the simple worker pattern).

## §11. `Codex CLI 미설치` or wrong codex binary path (for `sshee`-style bridges)

Not directly an agy issue — but if you're adapting this template for codex CLI bridges, ensure `which codex` returns the right binary and `codex --version` matches your expected release.

## §12. How to enable verbose logging for first-time debugging

Edit `bridge.py` `_dispatch` and add print statements between each step. The current template already has `[INBOX]` / `[OUTBOX]` / `_dispatch` trace lines — uncomment/expand if you need more.

For agy itself: pass `--debug` flag (if your agy version supports it). Otherwise just look at stderr in the bridge log.
