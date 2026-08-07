# claude-channel-server

A Slack bridge for Claude Code's [channel protocol](https://code.claude.com/docs/en/channels-reference) (`claude/channel`) — the mechanism that lets an external chat app inject messages into a running Claude Code session and receive replies back.

Two processes:

1. **`server.ts`** — a resident process. Holds the actual Slack Socket Mode connection and a Unix domain socket (`~/.claude/channels/slack/primary.sock`). Run it once, leave it running.
2. **`mcp.ts`** — a thin MCP stdio proxy. Claude Code spawns one of these per session. It has no Slack credentials of its own; it only talks to `server.ts` over the Unix socket and to Claude Code over stdio, translating between the two.

```
Slack  <--Socket Mode-->  server.ts  <--Unix socket-->  mcp.ts  <--stdio (MCP)-->  Claude Code session
```

This split exists so that one Slack app connection serves every Claude Code session you have open, instead of each session opening its own Socket Mode connection (which Slack will start rate-limiting/flapping under multiple concurrent connections for one app).

This is a from-scratch implementation written against the official channels-reference docs — not a copy of any existing bridge. If you're using this as teaching material: the two files worth reading closely for how the protocol actually works are `src/server.ts` (the Slack side) and `src/mcp.ts` (the MCP side).

## Setup

1. Create a Slack app (Socket Mode + Events API, `app_mention` and `message.channels` bot events, `chat:write` scope) and install it to your workspace. Invite the bot to the channel you want to bridge.
2. Install dependencies (not done automatically — see "Why no auto-install" below):
   ```bash
   npm install
   npm run build
   ```
3. Create the state directory and `.env`:
   ```bash
   mkdir -p ~/.claude/channels/slack
   cp .env.example ~/.claude/channels/slack/.env
   chmod 700 ~/.claude/channels/slack
   chmod 600 ~/.claude/channels/slack/.env
   $EDITOR ~/.claude/channels/slack/.env   # fill in real values, see .env.example
   ```
4. Start the resident server:
   ```bash
   npm start
   ```
   It logs `bridge live — channel ..., allowed user ...` on success. Leave it running (a terminal tab, `tmux`, a launchd/systemd unit — your choice; this project doesn't include a process manager).

## Registering the channel with Claude Code

Add the MCP server to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "slack-channel": {
      "command": "node",
      "args": ["/absolute/path/to/claude-channel-server/dist/mcp.js"]
    }
  }
}
```

Then start Claude Code with the channel opted in. During the research-preview period this requires one of:

```bash
# If you've published this as a plugin on an allowlisted marketplace:
claude --channels plugin:slack-channel@your-marketplace

# For local development against the .mcp.json entry above (this is the one
# you want while iterating on this project):
claude --dangerously-load-development-channels server:slack-channel
```

Both flags require your org's `channelsEnabled` policy to be on first (Console/API-key usage: on by default; claude.ai Team/Enterprise: an Owner has to enable it; Pro/Max without an org: no check). `--dangerously-load-development-channels` shows a one-time confirmation dialog ("I am using this for local development") and only bypasses the plugin allowlist check — not that master switch.

Once connected, a message you send in the configured Slack channel shows up in Claude's context as:

```
<channel source="slack" channel="C0000..." user="U0000..." ts="..." thread_ts="...">
your message text
</channel>
```

and Claude replies using the `reply` tool, which posts back to that channel (optionally threaded, if it echoes `thread_ts`).

## Security model

Three things this bridge enforces, and where:

**Sender gate — one choke point, forked by author kind.**
`src/server.ts` `handleSlackEvent` is the single choke point for every inbound Slack event. Human posts — regular messages, `@mentions`, and permission-approval replies (`yes <id>` / `no <id>`) — all get the same `event.user === env.ALLOWED_SLACK_USER_ID` check; there is no second code path with a weaker or missing check. Bot posts (bot-interop, 2026-08-07, optional) pass only if ALL of: not a DM, a real `user` (U…) that is not this bot itself, listed in `ALLOWED_SLACK_BOT_USER_IDS` (unset/empty = every bot drops — the legacy behavior, so existing installs regress zero), and the text explicitly `@`-mentions this bot. That mention-pass + allowlist pair is the entire ported Discord device — there is deliberately no message-count cap (a 6-cap was briefly shipped and measured cutting real bot meetings; conversations end by bot discipline, not by code). An allowed bot still cannot approve permission requests: the anchored verdict pattern can never contain the required mention.

**Hardening (a) — channel equality.**
Also in `handleSlackEvent`: `event.channel !== env.SLACK_CHANNEL_ID` is checked before anything else. This closes a real gap in the reference bridge this project was scoped against, which checked the sender but never the channel — so if that bot was later invited into an unrelated channel, anything the allowed user said there would have been forwarded too. Here, only the one configured channel is ever forwarded, regardless of what other channels the bot can see.

**Hardening (b) — Unix socket mode 0600 + peer UID verification.**
`src/server.ts` `startIpcServer`: the socket file is chmod'd to `0600` the instant `listen()` succeeds, before anything else runs. Independently of that, `src/peercred.ts` `verifyPeerIsSelf` looks up the connecting peer's effective UID on every incoming connection (macOS via `getpeereid(3)`, Linux via `getsockopt(2)`'s `SO_PEERCRED` — see "Platform support" below; both through `koffi`, no native compile step) and rejects the connection unless that UID matches this process's own UID. Filesystem permissions on the socket already stop other local users from `connect()`-ing at all — the peer-UID check is the second, independent gate for the edge cases file permissions alone don't cover (a root process, a brief window before the `chmod` lands, a misconfigured umask on the parent directory).

**Token handling.**
Real Slack tokens live only in `~/.claude/channels/slack/.env`, outside this repo, loaded by `src/config.ts` `loadEnv`. That function warns (doesn't silently proceed) if the file's mode isn't `0600`. Nothing in this codebase logs, echoes, or otherwise surfaces token values — if you're extending this and find yourself about to `console.log(env)`, don't; log the individual non-secret fields you need instead. `.env.example` in this repo contains only placeholders.

## Platform support

The peer-UID check (`src/peercred.ts`) implements two independent paths: macOS/BSD via `getpeereid(3)`, and Linux (glibc, `libc.so.6`/`libc.so`) via `getsockopt(2)`'s `SO_PEERCRED` option (`struct ucred { pid; uid; gid; }`, `SOL_SOCKET`=1, `SO_PEERCRED`=17 from `asm-generic/socket.h` — covers x86_64 and arm64, including WSL2). Security equivalence between the two paths is intentional: same fail-closed contract, same "reject unless peer euid == our euid" semantics. The macOS path is verified end-to-end on the actual deployment machine; the Linux path has passed `tsc`/`build` and code review but has not yet been run against a real Linux/WSL2 socket — treat it as implemented-but-unverified-in-the-field until confirmed there. On any platform other than macOS or Linux (e.g. native Windows without WSL), or if neither expected libc is loadable, `verifyPeerIsSelf` fails closed (rejects every connection) rather than silently skipping the check.

## Why no auto-install

`package.json` has no `postinstall`, `preinstall`, or `prestart` script, and `.mcp.json`-style launch commands for this project should call `node dist/mcp.js` directly, not something that triggers `npm install` on every session start. Dependencies are pinned to exact versions (no `^`/`~` ranges) — run `npm install` yourself when you actually want to pull them, and `npm outdated` if you want to know when pins have drifted from upstream.

## Development

```bash
npm run typecheck   # tsc --noEmit
npm run build        # tsc -> dist/
```

No test suite is included — the two `main()` entry points (`server.ts`, `mcp.ts`) are integration points against live Slack and live Claude Code stdio respectively, better verified by an actual round trip (send a message in Slack, watch it land in a running Claude Code session, send a reply, watch it show up in Slack) than by unit tests around them.
