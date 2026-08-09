#!/usr/bin/env node
// Resident bridge process: the ONLY thing that holds the Slack Socket Mode
// connection. Owns `~/.claude/channels/slack/primary.sock`; one or more
// `mcp.ts` proxies (one per Claude Code session) connect to it as IPC
// clients. Run this once and leave it running (see README "Running").
//
// Everything a message has to clear before it reaches a Claude Code
// session, in order:
//   1. Slack Socket Mode envelope ack (protocol requirement, not a gate)
//   2. event.channel === SLACK_CHANNEL_ID           (hardening a)
//   3. sender gate, split by author kind ((B) bot-interop, 2026-08-07):
//      a human post must be from ALLOWED_SLACK_USER_ID; a bot post must be
//      from ALLOWED_SLACK_BOT_USER_IDS (unset = every bot drops — the
//      pre-(B) behavior), must NOT be a DM, and must @-mention THIS bot
//   4. not an edit / join / self echo (subtype, own botUserId)
//   5. in a channel: the post must mention THIS bot (<@botUserId>) or be a
//      permission verdict — DMs are exempt (1:1, sender gate suffices)
//      (hardening c / target gate, 2026-08-06 defect 13)
//   6. not a duplicate delivery (message + app_mention can both fire)
// The IPC socket itself has its own, independent gate before any of the
// above even matters: mode 0600 + peer-uid verification (hardening b),
// see `startIpcServer` below and src/peercred.ts.

import { chmodSync, existsSync, unlinkSync } from 'node:fs';
import net from 'node:net';
import { SocketModeClient } from '@slack/socket-mode';
import { WebClient } from '@slack/web-api';
import { ENV_PATH, SOCKET_PATH, ensureStateDir, loadEnv, log } from './config.js';
import { ClientToServer, encodeLine, type ClientToServerMsg, type ServerToClientMsg } from './ipc-protocol.js';
import { LineReader } from './line-reader.js';
import { verifyPeerIsSelf } from './peercred.js';
import { acquireSingleton } from './singleton.js';

interface SlackMessageEvent {
  type?: string;
  subtype?: string;
  channel?: string;
  channel_type?: string;
  user?: string;
  text?: string;
  ts?: string;
  event_ts?: string;
  thread_ts?: string;
  bot_id?: string;
}

// Reference implementation for the permission-relay reply pattern, verbatim
// from the official channels-reference doc's "Add relay to a chat bridge"
// example — case-insensitive for autocorrect, `l` excluded from the id
// alphabet by Claude Code itself so it never appears here.
const VERDICT_PATTERN = /^\s*(y|yes|n|no)\s+([a-km-z]{5})\s*$/i;

function main(): void {
  if (process.platform !== 'darwin' && process.platform !== 'linux') {
    throw new Error(`unsupported platform ${process.platform} — this bridge requires a POSIX Unix socket`);
  }

  ensureStateDir();
  acquireSingleton();
  const env = loadEnv();

  const clients = new Set<net.Socket>();
  const seenTsOrder: string[] = [];
  const seenTsSet = new Set<string>();
  // Outbound allowlist: only conversations we've received an allowed inbound
  // from can be replied to — stops a reply from being routed to any other
  // channel/DM (DM content leak) even if a chat_id says otherwise.
  const allowedChannels = new Set<string>();
  // The most recent conversation an allowed inbound arrived from. Reply (when
  // chat_id is omitted) and permission-ask (which carries no channel at all)
  // fall back to this so DM-derived content lands in the active conversation
  // instead of always leaking to the public channel.
  let lastInboundChannel: string | null = null;
  // This bridge's own bot user id (U…), resolved once at startup via
  // `auth.test` — the target gate below needs it to decide "was I the one
  // being mentioned". Startup fails fast if it can't be resolved: an empty
  // value would silently drop every channel message (fail closed), which is
  // safe but undiagnosable.
  let botUserId = '';
  // Threads THIS bot is already part of (root ts). Follow-ups inside such a
  // thread pass the target gate without re-mentioning the bot — but only for
  // threads this bridge itself was pulled into, so with several bridge bots
  // in one channel the no-mention chorus (defect 13) does not come back:
  // each bot only exempts its own threads. Bounded like seenTs.
  const activeThreadsOrder: string[] = [];
  const activeThreadsSet = new Set<string>();
  function rememberThread(root: string): void {
    if (activeThreadsSet.has(root)) return;
    activeThreadsSet.add(root);
    activeThreadsOrder.push(root);
    if (activeThreadsOrder.length > 200) {
      const evicted = activeThreadsOrder.shift();
      if (evicted) activeThreadsSet.delete(evicted);
    }
  }

  // Outbound DM-thread guard (겹1, 2026-08-10 — 루돌프 실측 2026-08-09):
  // defect 17 taught handleSlackEvent (below) to only put `thread_ts` in a
  // DM's meta when the *inbound* message actually carried one — a DM the
  // user never threaded gets none, so the model has nothing legitimate to
  // echo. That is a code-side gate on the inbound path only, though; it does
  // nothing to the outbound `reply` tool, which accepts whatever thread_ts
  // argument the model hands it. When a model supplies one anyway (echoed
  // from an unrelated event, hallucinated, or just not following the
  // instruction), handleReply used to pass it straight to
  // chat.postMessage and Slack folds the DM into a comment thread — the
  // exact defect 17 symptom, resurrected through the tool-argument layer
  // instead of the code layer. channelKindByChannel + imInboundThreadTsSet
  // let handleReply veto that itself: only a thread_ts a real DM inbound
  // actually carried may be echoed back into a DM. Channel (non-DM) replies
  // are untouched — this guard only ever engages when the target channel is
  // 'im'.
  const channelKindByChannel = new Map<string, 'im' | 'other'>();
  const imInboundThreadTsOrder: string[] = [];
  const imInboundThreadTsSet = new Set<string>();
  function rememberImInboundThreadTs(threadTs: string): void {
    if (imInboundThreadTsSet.has(threadTs)) return;
    imInboundThreadTsSet.add(threadTs);
    imInboundThreadTsOrder.push(threadTs);
    if (imInboundThreadTsOrder.length > 200) {
      const evicted = imInboundThreadTsOrder.shift();
      if (evicted) imInboundThreadTsSet.delete(evicted);
    }
  }

  // (B) bot-interop (2026-08-07): which OTHER bridge bots may speak to this
  // one. U…-space on purpose — the same id axis as ALLOWED_SLACK_USER_ID and
  // as the `<@U…>` mention text, so there is exactly one id space to reason
  // about (the B…/U… split is what produced the live tag misread on
  // 2026-08-06). A bot message carries both `bot_id` (B…) and `user` (U…);
  // we key on `user` and drop authorless variants. Unset/empty = empty set =
  // every bot message drops — exactly the pre-(B) gate, so existing installs
  // regress zero.
  const allowedBotUserIds = new Set(
    (env.ALLOWED_SLACK_BOT_USER_IDS ?? '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  );
  // No bot-chain counter here on purpose (2026-08-07 재경님 "빼자"): the
  // Discord device this ports is mention-pass + allowlist, nothing more —
  // months of Discord operation and an 11-round human-free meeting show
  // conversations end by bot discipline, not by a code cap. A cap of 6 was
  // briefly shipped and measured cutting real work (see meeting 03-outcome
  // ⑦) — a low backstop stops being insurance and becomes the primary
  // control. Loop pressure is still bounded by ② explicit-mention + ①
  // allowlist below.

  function alreadySeen(ts: string): boolean {
    if (seenTsSet.has(ts)) return true;
    seenTsSet.add(ts);
    seenTsOrder.push(ts);
    if (seenTsOrder.length > 200) {
      const evicted = seenTsOrder.shift();
      if (evicted) seenTsSet.delete(evicted);
    }
    return false;
  }

  function broadcast(msg: ServerToClientMsg): void {
    const line = encodeLine(msg);
    for (const socket of clients) {
      if (!socket.destroyed) socket.write(line);
    }
  }

  function sendAck(socket: net.Socket, req_id: string, ok: boolean, error?: string): void {
    if (socket.destroyed) return;
    socket.write(encodeLine({ type: 'ack', req_id, ok, error }));
  }

  // ---- Slack Web API (outbound) -----------------------------------------

  const web = new WebClient(env.SLACK_BOT_TOKEN);

  async function handleReply(socket: net.Socket, msg: Extract<ClientToServerMsg, { type: 'reply' }>): Promise<void> {
    // Route to the conversation the session named (DM↔DM, channel↔channel),
    // but only if we've actually seen an allowed inbound from it; otherwise
    // fall back to the configured channel. Never post to an unseen chat_id.
    const target = msg.channel && allowedChannels.has(msg.channel) ? msg.channel : (lastInboundChannel ?? env.SLACK_CHANNEL_ID);
    // 겹1: strip a model-supplied thread_ts on a DM target unless it is one a
    // real DM inbound actually carried (see the guard comment above). Never
    // touches non-DM targets — msg.thread_ts passes through unchanged there,
    // same as before this fix.
    const isImTarget = channelKindByChannel.get(target) === 'im';
    const threadTs = isImTarget && !(msg.thread_ts && imInboundThreadTsSet.has(msg.thread_ts)) ? undefined : msg.thread_ts;
    try {
      await web.chat.postMessage({
        channel: target,
        thread_ts: threadTs,
        text: msg.text,
      });
      sendAck(socket, msg.req_id, true);
    } catch (err) {
      sendAck(socket, msg.req_id, false, err instanceof Error ? err.message : String(err));
    }
  }

  async function handleReact(socket: net.Socket, msg: Extract<ClientToServerMsg, { type: 'react' }>): Promise<void> {
    // Same outbound allowlist as reply: only react in conversations we've
    // actually received an allowed inbound from — a reaction placed in an
    // unseen chat would leak presence the same way a stray reply would.
    if (!allowedChannels.has(msg.channel)) {
      sendAck(socket, msg.req_id, false, `refusing to react in unseen conversation ${msg.channel}`);
      return;
    }
    const emoji = msg.emoji.replace(/^:+|:+$/g, ''); // accept ":thumbsup:" and "thumbsup" alike
    try {
      await web.reactions.add({ channel: msg.channel, timestamp: msg.ts, name: emoji });
      sendAck(socket, msg.req_id, true);
    } catch (err) {
      // Reacting twice with the same emoji is a no-op in spirit — report ok
      // so a retry doesn't read as a failure.
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes('already_reacted')) {
        sendAck(socket, msg.req_id, true);
        return;
      }
      sendAck(socket, msg.req_id, false, message);
    }
  }

  async function handlePermissionAsk(
    socket: net.Socket,
    msg: Extract<ClientToServerMsg, { type: 'permission_ask' }>,
  ): Promise<void> {
    const text = [
      `Claude wants to run ${msg.tool_name}: ${msg.description}`,
      msg.input_preview,
      '',
      `Reply "yes ${msg.request_id}" or "no ${msg.request_id}"`,
    ].join('\n');
    try {
      await web.chat.postMessage({ channel: lastInboundChannel ?? env.SLACK_CHANNEL_ID, text });
      sendAck(socket, msg.req_id, true);
    } catch (err) {
      sendAck(socket, msg.req_id, false, err instanceof Error ? err.message : String(err));
    }
  }

  // ---- Unix socket IPC (server side) -------------------------------------

  function handleClientLine(socket: net.Socket, raw: string): void {
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      log('ipc', 'dropped non-JSON line from client');
      return;
    }
    const result = ClientToServer.safeParse(parsed);
    if (!result.success) {
      log('ipc', `dropped malformed message: ${result.error.issues.map((i) => i.message).join('; ')}`);
      return;
    }
    const msg = result.data;
    switch (msg.type) {
      case 'register':
        clients.add(socket);
        log('ipc', `session ${msg.session_id} registered (${clients.size} active)`);
        break;
      case 'reply':
        void handleReply(socket, msg);
        break;
      case 'react':
        void handleReact(socket, msg);
        break;
      case 'permission_ask':
        void handlePermissionAsk(socket, msg);
        break;
    }
  }

  function startIpcServer(): net.Server {
    if (existsSync(SOCKET_PATH)) unlinkSync(SOCKET_PATH);

    const server = net.createServer((socket) => {
      // Hardening (b): mode 0600 on the socket file already stops other
      // local users from opening() it at all — this is the second,
      // independent check: reject unless the connecting process's
      // effective uid is literally our own.
      if (!verifyPeerIsSelf(socket)) {
        log('ipc', 'rejected connection: peer uid does not match this process');
        socket.destroy();
        return;
      }

      const reader = new LineReader((line) => handleClientLine(socket, line));
      socket.on('data', (chunk) => reader.push(chunk));
      socket.on('close', () => clients.delete(socket));
      socket.on('error', (err) => log('ipc', `client socket error: ${err.message}`));
    });

    server.listen(SOCKET_PATH, () => {
      // Hardening (b): tighten immediately after bind — the socket file
      // exists the instant listen() succeeds, so we chmod before yielding
      // control back to the event loop (no `await` between listen() and
      // this callback).
      chmodSync(SOCKET_PATH, 0o600);
      log('ipc', `listening on ${SOCKET_PATH} (mode 0600)`);
    });

    server.on('error', (err) => log('ipc', `server error: ${err.message}`));
    return server;
  }

  // ---- Slack Socket Mode (inbound) ---------------------------------------

  async function handleSlackEvent(event: SlackMessageEvent): Promise<void> {
    // Hardening (a): the channel this event came from must be the one
    // configured channel, OR the event must be a DM (channel_type 'im') —
    // purujitgoyal's reference bridge never checked this (see spec's
    // gapChannelEquality), so a bot invited into any other channel would
    // forward everything from there too. DM is let through here because the
    // sender gate right below is the sole guard on that path (see spec 44
    // §②): a DM is inherently 1:1 with whoever sent it, so once that sender
    // is verified as ALLOWED_SLACK_USER_ID there is no other channel this
    // event could have leaked from.
    if (event.channel !== env.SLACK_CHANNEL_ID && event.channel_type !== 'im') return;

    const text = (event.text ?? '').trim();

    // Sender gate, split by author kind ((B) bot-interop, 2026-08-07). Order
    // trap, measured live by 루돌프 before this change shipped: the old
    // human-only check sat ABOVE the bot gate, and a bot post carries its own
    // U… in event.user — so it died at the human check and never reached the
    // bot line. "Relax the bot_id line" alone would have opened nothing while
    // building green. The two judgments therefore live in one fork now.
    const fromBot = Boolean(event.bot_id) || event.subtype === 'bot_message';
    if (!fromBot) {
      // Human path — same ALLOWED_SLACK_USER_ID check as always, for
      // messages, @mentions, and permission-verdict replies alike.
      if (event.user !== env.ALLOWED_SLACK_USER_ID) return;
      if (event.subtype) return; // edits, joins, etc.
    } else {
      // DMs stay human-only: the DM path's whole security argument (spec 44
      // §②) is "1:1 with a verified human". Bot conversations belong in the
      // channel, where the mention discipline below applies.
      if (event.channel_type === 'im') return;
      if (!event.user || event.user === botUserId) return; // self echo / authorless variants
      if (!allowedBotUserIds.has(event.user)) return; // not an allowed peer (empty set = pre-(B) behavior)
      // A bot must name THIS bot explicitly — no verdict shortcut and no
      // thread exemption for bot senders. Defense in depth: the anchored
      // VERDICT_PATTERN can never contain a mention, so an allowed bot also
      // cannot approve permission requests through this gate.
      if (!text.includes(`<@${botUserId}>`)) return;
    }

    // Hardening (c) — target gate (2026-08-06, defect 13): `message.channels`
    // is subscribed, so EVERY channel post from the allowed user reaches every
    // bridge attached to that channel — N bridge bots would all answer any
    // message (live incident: three bots chorused one greeting). In a channel
    // the post must name THIS bot to proceed. Two deliberate exemptions:
    //   - DMs (`channel_type === 'im'`): 1:1 by construction, the sender gate
    //     above suffices (same argument as gate 2's DM branch, spec 44 §②).
    //   - Permission verdicts ("yes abcde"): intentionally carry no mention,
    //     so they'd be silently dropped and approvals would never land —
    //     quiet breakage, the worst kind (defect 13 prescription #3).
    //   - Follow-ups in a thread this bot already participates in (defect 17
    //     interaction): channel replies are threaded, and requiring a fresh
    //     @-mention for every follow-up inside the bot's own thread would
    //     make conversations unusable. Scoped to activeThreadsSet, see above.
    //     T4 refinement (2026-08-06): the thread exemption applies only to
    //     MENTION-FREE follow-ups — the moment the user explicitly mentions
    //     someone (<@U…>/<@W…>), explicit addressing wins ("태그한 봇만
    //     답해야" applies inside threads too). So in my thread: no mention →
    //     implicitly mine, pass; mentions me → pass; mentions only another
    //     bot → I stay silent.
    const hasAnyUserMention = /<@[UW][A-Z0-9]+>/.test(text);
    if (
      event.channel_type !== 'im' &&
      !VERDICT_PATTERN.test(text) &&
      !text.includes(`<@${botUserId}>`) &&
      !(event.thread_ts && activeThreadsSet.has(event.thread_ts) && !hasAnyUserMention)
    ) return;

    const ts = event.event_ts ?? event.ts;
    if (!ts || alreadySeen(ts)) return; // 'message' and 'app_mention' can both fire for one post

    if (event.channel) {
      allowedChannels.add(event.channel); // this conversation is now a valid reply target
      lastInboundChannel = event.channel; // ...and the active one for fallback routing
      channelKindByChannel.set(event.channel, event.channel_type === 'im' ? 'im' : 'other'); // 겹1: which reply-target-guard branch applies
    }

    // 겹1: record a genuine DM thread_ts (the user actually opened a thread
    // in this DM) so handleReply's guard above can tell that apart from a
    // model-supplied one. Channels don't need this — the guard never strips
    // their thread_ts.
    if (event.channel_type === 'im' && event.thread_ts) {
      rememberImInboundThreadTs(event.thread_ts);
    }

    // Defect 17: in a channel this conversation now lives in a thread rooted
    // at the inbound message (or the thread it was already in) — remember the
    // root so follow-ups inside it pass the target gate without a re-mention.
    if (event.channel_type !== 'im') {
      rememberThread(event.thread_ts ?? ts);
    }

    const verdictMatch = VERDICT_PATTERN.exec(text);
    if (verdictMatch) {
      const [, verb, requestId] = verdictMatch;
      broadcast({
        type: 'permission_verdict',
        request_id: (requestId ?? '').toLowerCase(),
        behavior: (verb ?? '').toLowerCase().startsWith('y') ? 'allow' : 'deny',
      });
      return;
    }

    broadcast({
      type: 'inbound',
      content: text,
      meta: {
        // Must be the real event.channel/event.user, not the env values:
        // with DM support (spec 44 §③) a DM's channel is D… and a
        // channel post's is C…, and env.SLACK_CHANNEL_ID is only ever the
        // latter — hardcoding it here would route every DM reply back out
        // to the public channel instead of the DM it came from. The `??`
        // fallback is defensive only: both fields are guaranteed present
        // by the gate above (channel matched one of two known-non-empty
        // forms, user matched the sender gate — human or allowed bot), so
        // this never actually falls through in practice — it just keeps the
        // optional typing honest without an assertion.
        channel: event.channel ?? env.SLACK_CHANNEL_ID,
        user: event.user ?? env.ALLOWED_SLACK_USER_ID,
        ts: event.ts ?? ts,
        // Lets the session tell an allowed peer bot from the human without a
        // roster lookup — meta is Record<string, string>, hence the string
        // 'true' and the conditional spread ((B) bot-interop, 2026-08-07).
        ...(fromBot ? { sender_is_bot: 'true' } : {}),
        // Threading is scoped by conversation kind (2026-08-06 defect 17):
        //   - CHANNEL: always thread — reply lands under the message that
        //     summoned the bot (synthesize the root from event.ts when the
        //     inbound is itself top-level), so the channel doesn't fill up
        //     with bot answers ("스레드 답글로 달아야" — user requirement).
        //   - DM: thread only when the user themselves threaded. The earlier
        //     uniform event.ts fallback forced every 1:1 reply into an
        //     awkward 댓글 thread — that rationale still holds, but only for
        //     DMs; scoping (not reverting) is what defect 17 asked for.
        // Conditional spread keeps the Record<string, string> meta type
        // honest (no undefined value).
        ...(event.thread_ts
          ? { thread_ts: event.thread_ts }
          : event.channel_type !== 'im'
            ? { thread_ts: event.ts ?? ts }
            : {}),
      },
    });
  }

  const socketModeClient = new SocketModeClient({ appToken: env.SLACK_APP_TOKEN });

  socketModeClient.on('message', async ({ event, ack }) => {
    await ack();
    await handleSlackEvent(event as SlackMessageEvent);
  });

  socketModeClient.on('app_mention', async ({ event, ack }) => {
    await ack();
    await handleSlackEvent(event as SlackMessageEvent);
  });

  socketModeClient.on('error', (err) => log('slack', `socket mode error: ${err instanceof Error ? err.message : String(err)}`));

  // ---- lifecycle ----------------------------------------------------------

  const ipcServer = startIpcServer();
  let shuttingDown = false;

  async function shutdown(signal: string): Promise<void> {
    if (shuttingDown) return;
    shuttingDown = true;
    log('server', `received ${signal}, shutting down`);
    try {
      await socketModeClient.disconnect();
    } catch {
      /* best effort */
    }
    ipcServer.close(() => {
      if (existsSync(SOCKET_PATH)) unlinkSync(SOCKET_PATH);
      process.exit(0);
    });
    setTimeout(() => process.exit(0), 3000).unref();
  }

  process.on('SIGINT', () => void shutdown('SIGINT'));
  process.on('SIGTERM', () => void shutdown('SIGTERM'));

  // Resolve our own bot user id BEFORE opening the event stream — the target
  // gate (hardening c) compares inbound text against `<@${botUserId}>`, and
  // starting with an empty id would fail closed on every channel message with
  // no symptom. Fail fast and loud instead.
  web.auth
    .test()
    .then((auth) => {
      botUserId = String(auth.user_id ?? '');
      if (!botUserId) throw new Error('auth.test returned no user_id — cannot arm the mention target gate');
      log('server', `bot user resolved — ${botUserId}`);
      return socketModeClient.start();
    })
    .then(() =>
      log(
        'server',
        `bridge live — channel ${env.SLACK_CHANNEL_ID}, allowed user ${env.ALLOWED_SLACK_USER_ID}, bot ${botUserId} ` +
          `(channel posts require @-mention; DMs and permission verdicts exempt; bot interop ` +
          `${allowedBotUserIds.size > 0 ? `enabled — ${allowedBotUserIds.size} peer(s)` : 'disabled'})`,
      ),
    )
    .catch((err) => {
      log('server', `failed to start Slack bridge: ${err instanceof Error ? err.message : String(err)}`);
      process.exit(1);
    });

  log('server', `env loaded from ${ENV_PATH}`);
}

main();
