# references/agy-vs-claude-codex-ipc.md

**Why this exists**: People often ask "I have `agy` running, why can't I just hook it up to Discord the same way the codex/claude bots do?" Short answer: agy 1.0 has no documented server mode. This doc breaks down what each CLI exposes, why agy needs a different bridge shape, and how to operate the resulting hs bridge.

Empirically verified: 2026-05-21 agy 1.0.0 / codex 0.132.0 / claude 5.x on Mac.

## TL;DR

| CLI | Server mode? | Bridge pattern | Two-way IPC | Stateful across calls |
|---|---|---|---|---|
| **codex** (OpenAI) | YES — `codex app-server --listen ws://...` | bridge ↔ WebSocket JSON-RPC ↔ codex daemon | yes | thread-id resume |
| **claude code** (Anthropic) | NO server mode, but **MCP-as-client** + interactive REPL | bridge wraps a tmux pty + sends keys, OR uses claude code as a one-shot subprocess | partial — depends on which surface | session state in `~/.claude` |
| **agy** (Google Antigravity) | **NO** — neither server nor `--listen` flag exists in 1.0 | bridge spawns `agy --print` as a subprocess per Discord message; output via stdout only | **NO** (single-direction request/response) | `--conversation <uuid>` for thread continuity |

If you skip everything below, the operational consequence is: **agy bridges are forced into a fire-and-forget shape**. They cannot stream tokens to Discord, they cannot reflect tool calls live, they cannot receive a follow-up from agy mid-response. Every Discord message becomes a new subprocess call.

---

## 1. codex — WebSocket app-server (the only "real" two-way IPC of the three)

### What codex exposes

```
codex app-server --listen ws://127.0.0.1:4222
```

- Long-running daemon, opens a WebSocket on the given address.
- Speaks **JSON-RPC 2.0** (`jsonrpc2Message`, `jsonrpc2Request` symbols in the binary).
- Bridge client sends `thread/start`, `turn/start`, `turn/cancel`; receives streamed `item/agentMessage/delta`, `turn/completed`, `mcpServer/startupStatus/updated`, `account/rateLimits/updated`, `hook/started`, `hook/completed`, etc.
- Bridge can `codex resume <thread-id>` to attach a TUI to the **same** thread the bridge is driving — multi-client same-thread (empirically confirmed 2026-05-15 with codex `c-2` client). This is what makes the sshee 2-window pattern possible: `infra` window runs the app-server + bot.py daemon, `codex` window attaches a TUI to the same thread as a second client.

### Bridge shape (sshee = `AI_Second_Brain/.discord-bots/sonseokhee/`)

```
Discord → bot.py (on_message) → ws://127.0.0.1:4222 → codex daemon
                                       ↑
                                       └── codex TUI (codex resume <tid>) attaches as 2nd client
```

- `launch.sh` foregrounds `bot.py`, backgrounds `codex app-server`, traps cleanup.
- bot.py persists the active thread id to `.codex-thread-id` so the TUI window's `until [ -s .codex-thread-id ]; do sleep 1; done; codex resume "$TID"` can attach.
- The user gets:
  - Discord-facing turn streaming via the bridge.
  - Local TUI view of the same conversation (read-only-ish — second client can also send, but typically the user just observes).

### Operational consequences

- **Two-way streaming works**: `item/agentMessage/delta` arrives as the model emits; bridge can forward to Discord with `edit_message` (or wait for `turn/completed` and post once).
- **Cancellation works**: bridge can send `turn/cancel` on user request.
- **Multi-client same-thread**: a Discord-driven turn shows up in the local TUI window in real time. Powerful for debugging.
- **MCP-as-client**: codex itself uses MCP to call tools (`mcpServer/startupStatus/updated` in the log). The bridge does not need to expose MCP unless it wants to add custom tools.

### Failure modes seen

- Port collision: a lingering `codex app-server` on `:4222` blocks restart. Fix: `lsof -ti tcp:4222 | xargs kill`.
- Suicide-guard / wrapper conflicts: if you wrap `launch.sh` in your shell to manage tmux sessions, do not also have `launch.sh` re-create the session (see §5).
- WebSocket disconnect: bot.py needs reconnect logic. sshee uses a `while true; do ./launch.sh; sleep 5; done` watchdog in the `infra` tmux window.

---

## 2. claude code — no server mode, but rich MCP-as-client + interactive REPL

### What claude code exposes

- **Interactive REPL** in a tty: `claude` opens a TUI prompt. Subprocesses can drive it via a pty (write to master fd, drain slave) or via tmux `send-keys`.
- **One-shot subprocess**: `claude --print "<prompt>"` (or `-p`) returns once and exits. No streaming.
- **MCP server registry**: claude code is an MCP **client**. It calls MCP servers you list in its settings. It does **not** itself listen on a port for external bridge clients.
- **Hooks**: SessionStart, Stop, UserPromptSubmit etc., shell-script triggered. Useful for injection at session boundaries, not for live two-way IPC.

### Common Discord bridge patterns

| Pattern | Two-way? | Notes |
|---|---|---|
| **tmux send-keys** to a claude REPL pane | partial — you can type prompts in, but capturing structured output requires scraping the pane | brittle; what the early hs bridge tried |
| **pty wrapper** in Python (`pty.openpty()`) | yes, but parsing the TUI's redraws is fragile | works for "ask one thing, drain output until 500ms quiet" |
| **`claude --print` subprocess per message** | no streaming, request/response only | clean, no state across calls unless you persist `~/.claude/projects/...` manually |
| **claude code as an MCP server** | NO — claude is not an MCP server | this is a common misconception |
| **Custom MCP server you author, claude calls it** | inverted IPC — claude becomes the client of your tool | works for adding capabilities, not for "Discord → claude → response" |

The Anthropic-blessed shape today is: write your own MCP server, register it with claude code, and let claude call your tool. That's the inverse of what a chat-bridge wants.

### When you'd still use claude code for a chat bridge

- One-shot `claude --print` per Discord message is fine for simple Q&A. No streaming, no thread state, but it works.
- For session continuity, persist the claude project directory yourself per Discord channel (mkdir `~/.claude/projects/<safe-ch>/`).

---

## 3. agy (Antigravity 1.0) — single-shot subprocess only

### What agy exposes (empirically, `agy --help` 2026-05-21)

```
Usage of /Users/<you>/.local/bin/agy:
  --add-dir         Add a directory to the workspace (repeatable)
  -c / --continue   Continue the most recent conversation
  --conversation    Resume a previous conversation by ID
  --dangerously-skip-permissions
  --log-file        Override CLI log file path
  -p / --print      Run a single prompt non-interactively and print the response
  --print-timeout   Timeout for print mode wait (default 5m0s)
  --prompt          Alias for --print
  --prompt-interactive  Run an initial prompt interactively and continue
  --sandbox         Sandbox with terminal restrictions

Subcommands:
  changelog / help / install / plugin / plugins / update
```

There is no `serve`, `--listen`, `--daemon`, or `mcp serve` flag. The binary contains MCP **client** symbols (`mcp_servers`, `mcp_tool`, `MCP_SERVER_STATUS_*`, `McpAuth`, `McpCommandTemplate`, `jsonrpc2Message`, `jsonrpc2Request`), but these are all on the consumer side — agy can call MCP servers you give it, agy does not become one.

`agy plugin` is an **importer**, not a server:

```
plugin commands:
  list           # imported plugins
  import         # from gemini or claude
  install <target>   # supports plugin@marketplace
  uninstall / enable / disable / validate / link
```

`agy plugin install --help` errors with `failed to read plugin.json` — confirming plugins are read from a `plugin.json` manifest on disk, the same pattern claude/Hermes plugins use. There is no "agy hosts an addressable surface" mode.

### Why this forces the hs bridge shape

If agy cannot be hosted as a daemon and cannot speak to a client over WebSocket / MCP, the bridge has exactly one move: **spawn `agy --print` per Discord message**.

```
Discord on_message → bridge worker → agy --print --conversation <uuid> ... → stdout → Discord reply
```

- **No streaming** — Discord users wait until agy finishes the full turn.
- **No mid-turn signals** — bridge cannot cancel, cannot inject context mid-thought.
- **Persona injection is manual** — `agy --print` does **not** auto-load `GEMINI.md` (only the interactive `--prompt-interactive` mode does). The bridge has to prepend persona text to every prompt.
- **`--conversation <uuid>`** keeps a thread alive across spawns, but each spawn is still a fresh process: cold-start cost on every Discord message.

This is the pattern in `agent-hassabis/scripts/bridge.py` `_dispatch` → `agy.run_y3`.

### Why "two-way" via agy is currently impossible (B-original / C from the 2026-05-21 agy-ipc-b-decision-security meeting)

- **B-original** (treat agy itself as a server the bridge calls): BLOCK. The server doesn't exist.
- **C** (mirror codex's WebSocket JSON-RPC pattern): BLOCK. Same reason — agy is not a server.
- **B-inverted** (hs hosts an MCP server, agy connects as MCP client and calls hs tools): technically possible because agy IS an MCP client. But this is "agy can call us" not "we drive agy" — it does not make Discord ↔ agy streaming work. And it opens a large security surface (see `references/permission-overwrite-ledger.md`, `09-security-review-hs-server-pattern.md` §3).

If/when agy gets an `agy serve` or `agy --listen` mode, re-evaluate. Until then, the single-shot subprocess shape is the right one.

---

## 4. The visible-feedback question (tmux send-keys to a TUI window)

Earlier hs bridge versions also `send-keys`'d every Discord message into a tmux pane running `agy` interactively, just so the operator could *see* the message appear in the agy TUI. The agy TUI didn't actually process it — the real processing was the parallel `agy --print` subprocess.

This was removed 2026-05-21 on the operator's call: "Discord is the user UI, the tmux inject is redundant." If you fork this skill and want the visible feedback back, the function was `Bridge._tmux_inject` and the env var was `AGY_TUI_PANE`.

For codex bridges this is **not** redundant — the codex TUI window genuinely attaches to the same thread the bridge is driving, so visible feedback there is real conversation state, not a decorative replay.

---

## 5. Operating an agy-style bridge (hs / Antigravity Discord bot)

### Standard launch (cold start)

```bash
cd ~/path/to/agent-hassabis
BOT_NAME=mybot bash scripts/launch.sh   # default BOT_NAME=hs
# tmux session $BOT_NAME with 2 windows: agy (TUI, optional manual use) + daemon (bridge log)
```

The agy window runs `agy --sandbox` (or `--dangerously-skip-permissions` if you've set `AGY_UNSAFE=1` in `.env`) just so you can manually drive agy if you want. The bridge does not touch this window after 2026-05-21 (the visible-inject was removed).

### Restart from inside the bot's own tmux session

The `launch.sh` no longer has an internal wrapper block (removed 2026-05-21 to fix a sshee-style "kill-own-session" bug, see §6). To restart the bot from inside its own session:

1. Detach (`C-b d`) → run `BOT_NAME=$NAME bash ~/path/to/launch.sh` from your shell.
2. Or wrap the launch in a shell function that detects "called from inside the bot session" and bootstraps via a side session.

Example zsh function (the hs/sshee shape):

```bash
hs() {
  local cur=""
  [ -n "${TMUX:-}" ] && cur="$(tmux display-message -p '#S' 2>/dev/null)"
  if [ "$cur" = "hs" ]; then
    local boot="hs-restart-$$"
    tmux new-session -d -s "$boot" -n restart \
      "sleep 0.3; zsh -lc 'cd ~/path/to/agent-hassabis && bash scripts/launch.sh; tmux switch-client -t hs; tmux kill-session -t $boot'"
    tmux switch-client -t "$boot"
    return
  fi
  cd ~/path/to/agent-hassabis && bash scripts/launch.sh
}
```

### Logs

- bridge daemon: `state/logs/YYYY-MM-DD/bridge-launch.log` (mode 700 dir, mode 600 file)
- agy own log: per `--log-file` (default in `~/.claude/...` or wherever agy is configured)

### Heartbeat / liveness

bridge prints `[HH:MM:SS] <bot> alive — queue=N channels=N` every 30s to the daemon window. If you see heartbeat ticking but `queue=0 channels=0` after a known mention, you're hitting the OAuth-or-channel-overwrite issue documented in `references/troubleshooting.md` §1.

### Permission overwrites (when you grant channel access to the bot)

Record every overwrite in `state/permission-ledger.jsonl` per the schema in `references/permission-overwrite-ledger.md`. This is a HARD gate for any future surface expansion (B-inverted etc).

---

## 6. The lesson from sshee's "exited immediately" bug (2026-05-21)

When the same project also has a shell-function bootstrap (zsh `_<bot>_rebuild_session`) that creates a 2-window tmux pattern (infra + secondary client window), do **not** also have `launch.sh` do its own `tmux kill-session -t <bot>` + `tmux new -s <bot> -d` wrapper. The two layers race:

1. zshrc bootstrap creates the session with `tmux new-session -d -s <bot> -n infra ... ./launch.sh ...`.
2. `launch.sh` enters its wrapper block, sees the (just-created) session, kills it, and tries to recreate.
3. Killing the session takes down the infra window, which was the very process running launch.sh. The while-true watchdog inside the window breaks, and the user's `tmux attach -t <bot>` shows "[exited]".

Fix: pick ONE layer to own session lifecycle. We chose the zshrc bootstrap (it has richer logic — port cleanup, bot-sync pull, .codex-thread-id reset). `launch.sh` is now pure runner.

The codex bridge (sshee) hit this on 2026-05-21 because we removed its in-launch suicide guard the day before but left the wrapper block in place. The same trap is possible in any bridge that copies this pattern — don't ship `launch.sh` with a wrapper block if you're also wrapping it externally.

---

## 7. Mapping back to the agy IPC decision

The 2026-05-21 agy-ipc-b-decision-security meeting (vault `AI_Second_Brain/meetings/2026-05-21-agy-ipc-b-decision-security/`) decided:

- agy → single-shot subprocess via `agy --print`, persona prepended manually, `--conversation <uuid>` for thread continuity. This is the only currently supported shape.
- Two-way / streaming / hosted-agy approaches are blocked on agy CLI getting a server mode upstream.

Re-read that meeting's `03-outcome.md` before changing the bridge architecture.
