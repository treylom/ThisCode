#!/usr/bin/env node
// Resident bridge process: the ONLY thing that holds the Slack Socket Mode
// connection. Owns `~/.claude/channels/slack/primary.sock`; one or more
// `mcp.ts` proxies (one per Claude Code session) connect to it as IPC
// clients. Run this once and leave it running (see README "Running").
//
// Everything a message has to clear before it reaches a Claude Code
// session, in order:
//   1. Slack Socket Mode envelope ack (protocol requirement, not a gate)
//   2. event.channel is one of SLACK_CHANNEL_ID     (hardening a)
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
import { ANY_MEMBER_CHANNEL, ENV_PATH, SOCKET_PATH, ensureStateDir, loadEnv, log, parseChannelIds } from './config.js';
import { ClientToServer, encodeLine, type ClientToServerMsg, type ServerToClientMsg } from './ipc-protocol.js';
import { LineReader } from './line-reader.js';
import { pickInboundDoneKey } from './pending-key.js';
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
  // Multi-channel (2026-08-13): the bridge may sit in several channels at
  // once. `configuredChannels` is what gate (a) below tests membership
  // against; `primaryChannelId` (the first id) is the outbound fallback for
  // messages that carry no channel of their own — permission asks. A
  // single-id .env therefore behaves identically to before this change.
  const parsedChannelIds = parseChannelIds(env.SLACK_CHANNEL_ID);
  // `*` (ANY_MEMBER_CHANNEL, config.ts): also forward from every channel the
  // bot has been invited to — the invite is the allowlist.
  const listenAnyMemberChannel = parsedChannelIds.includes(ANY_MEMBER_CHANNEL);
  const configuredChannelIds = parsedChannelIds.filter((id) => id !== ANY_MEMBER_CHANNEL);
  const primaryChannelId = configuredChannelIds[0]!;
  const configuredChannels = new Set(configuredChannelIds);
  function isListenedChannel(channel: string | undefined, channelType: string | undefined): boolean {
    if (!channel) return false;
    if (configuredChannels.has(channel)) return true;
    // Slack delivers channel/group events only for conversations the bot is a
    // member of, so with the wildcard "member" is already established.
    return listenAnyMemberChannel && (channelType === 'channel' || channelType === 'group');
  }
  // Per-bot receipt emoji (2026-09-23) — see SLACK_BOT_EMOJI in config.ts.
  const receiptEmoji = (env.SLACK_BOT_EMOJI ?? 'eyes').replace(/^:+|:+$/g, '') || 'eyes';

  const clients = new Set<net.Socket>();
  const seenTsOrder: string[] = [];
  const seenTsSet = new Set<string>();
  // Outbound allowlist: only conversations we've received an allowed inbound
  // from can be replied to — stops a reply from being routed to any other
  // channel/DM (DM content leak) even if a chat_id says otherwise.
  // Seeded with the configured channels (2026-09-23): a session may address a configured
  // channel explicitly from the first send, instead of falling back to the home channel
  // until an inbound from it has been seen (three misdeliveries in one morning). DMs and
  // any other conversation still have to be seen first.
  const allowedChannels = new Set<string>(configuredChannelIds);
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
    // Bounded at 200 (FIFO): past that, the oldest tracked DM thread is evicted
    // first. That thread's next reply then falls back to the DM body outside
    // any thread instead of being echoed into it — still delivered, just no
    // longer thread-anchored. Graceful degradation, not silent loss or misdelivery.
    if (imInboundThreadTsOrder.length > 200) {
      const evicted = imInboundThreadTsOrder.shift();
      if (evicted) imInboundThreadTsSet.delete(evicted);
    }
  }

  // Auto progress reactions (2026-09-23): which inbound is still "being
  // worked on" per conversation thread, so the reply that closes it can swap
  // 👀 for ✅ on that exact message. Keyed `${channel}:${thread root}`; bounded
  // at 200 FIFO like the other trackers — an evicted entry just means no ✅.
  const pendingInboundByThread = new Map<string, { channel: string; ts: string }>();
  const newestPendingKeyByChannel = new Map<string, string>();
  function rememberPendingInbound(key: string, ref: { channel: string; ts: string }): void {
    pendingInboundByThread.delete(key);
    pendingInboundByThread.set(key, ref);
    newestPendingKeyByChannel.set(ref.channel, key); // a top-level DM reply closes this one
    if (pendingInboundByThread.size > 200) {
      const oldest = pendingInboundByThread.keys().next().value;
      if (oldest !== undefined) pendingInboundByThread.delete(oldest);
    }
  }
  async function markInboundDone(key: string): Promise<void> {
    const ref = pendingInboundByThread.get(key);
    if (ref && newestPendingKeyByChannel.get(ref.channel) === key) newestPendingKeyByChannel.delete(ref.channel);
    if (!ref) return;
    pendingInboundByThread.delete(key);
    // The per-bot receipt emoji stays (it is the "who read this" record); ✅ is added
    // beside it so the count of ✅ reads as "how many bots finished".
    try {
      await web.reactions.add({ channel: ref.channel, timestamp: ref.ts, name: 'white_check_mark' });
    } catch (err) {
      const m = err instanceof Error ? err.message : String(err);
      if (!m.includes('already_reacted')) log('react', `check on ${ref.channel}/${ref.ts} failed: ${m}`);
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
    // Route to the conversation the session named (DM↔DM, channel↔channel).
    // A named chat_id must be one we may post to (configured, seen an allowed
    // inbound from, or — with the `*` wildcard — any non-DM channel; Slack
    // itself rejects a channel the bot is not in). A chat_id outside that set
    // is an ERROR back to the session, not a silent fallback: a reply that
    // lands in the home channel instead of the maintainer's DM looks like
    // "sent" to the model and is found hours later (2026-09-23, four such
    // misdeliveries). The fallback (last inbound, else primary) applies only
    // when the session named no chat_id at all.
    if (msg.channel && !allowedChannels.has(msg.channel) && !(listenAnyMemberChannel && !msg.channel.startsWith('D'))) {
      sendAck(socket, msg.req_id, false, `chat_id ${msg.channel} is not a conversation this bridge may post to (no allowed inbound seen from it) — reply NOT sent`);
      return;
    }
    const target = msg.channel ?? lastInboundChannel ?? primaryChannelId;
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
      // ✅ beside the receipt emoji on the inbound this reply answers: the thread
      // root when threaded, the newest pending inbound of the DM when a DM reply
      // is top-level (pending-key.ts). Fire-and-forget.
      const doneKey = pickInboundDoneKey(target, threadTs, isImTarget, newestPendingKeyByChannel);
      if (doneKey) void markInboundDone(doneKey);
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
      await web.chat.postMessage({ channel: lastInboundChannel ?? primaryChannelId, text });
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
    if (!isListenedChannel(event.channel, event.channel_type) && event.channel_type !== 'im') return;

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
    // Only a thread the user opened counts (2026-09-23: DM replies are
    // top-level unless the user wrote inside a thread) — the inbound's own ts
    // is deliberately NOT registered, so a model that echoes it as thread_ts
    // gets it stripped by handleReply's guard and the DM reply stays
    // top-level, where it raises a notification.
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

    // Auto progress reaction (2026-09-23, user request): the bot's receipt emoji
    // (SLACK_BOT_EMOJI, default 👀) the moment an inbound is accepted, plus ✅
    // once the session's reply is posted (handleReply). Best-effort — a failed
    // reaction never blocks delivery.
    if (event.channel) {
      const inboundChannel = event.channel;
      void web.reactions
        .add({ channel: inboundChannel, timestamp: ts, name: receiptEmoji })
        .catch((err) => log('react', `${receiptEmoji} on ${inboundChannel}/${ts} failed: ${err instanceof Error ? err.message : String(err)}`));
      rememberPendingInbound(`${inboundChannel}:${event.thread_ts ?? ts}`, { channel: inboundChannel, ts });
    }

    broadcast({
      type: 'inbound',
      content: text,
      meta: {
        // Must be the real event.channel/event.user, not the env values:
        // with DM support (spec 44 §③) a DM's channel is D… and a
        // channel post's is C…, and primaryChannelId is only ever the
        // latter — hardcoding it here would route every DM reply back out
        // to the public channel instead of the DM it came from. The `??`
        // fallback is defensive only: both fields are guaranteed present
        // by the gate above (channel matched one of two known-non-empty
        // forms, user matched the sender gate — human or allowed bot), so
        // this never actually falls through in practice — it just keeps the
        // optional typing honest without an assertion.
        channel: event.channel ?? primaryChannelId,
        user: event.user ?? env.ALLOWED_SLACK_USER_ID,
        ts: event.ts ?? ts,
        // Lets the session tell an allowed peer bot from the human without a
        // roster lookup — meta is Record<string, string>, hence the string
        // 'true' and the conditional spread ((B) bot-interop, 2026-08-07).
        ...(fromBot ? { sender_is_bot: 'true' } : {}),
        // Threading: in a CHANNEL the reply always lands under the message
        // that summoned the bot — the thread the inbound was in, else the
        // inbound itself becomes the root (defect 17, 2026-08-06: a channel
        // must not fill up with bot answers). In a DM the reply is top-level
        // unless the user themselves wrote inside a thread: a threaded DM
        // reply raises no notification on the user's side (maintainer,
        // 2026-09-23 — the brief "always thread DMs" experiment was reverted
        // the same day for exactly that reason). Conditional spread keeps
        // the Record<string, string> meta type honest (no undefined value).
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
        `bridge live — channels ${configuredChannelIds.join(', ')}${listenAnyMemberChannel ? ' + any channel the bot is a member of (*)' : ''}, allowed user ${env.ALLOWED_SLACK_USER_ID}, bot ${botUserId} ` +
          `(channel posts require @-mention; DMs and permission verdicts exempt; auto-react on (receipt ${receiptEmoji}); bot interop ` +
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
