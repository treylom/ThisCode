// Silent-drop notice + record for the Slack bridge. Pure functions and a small
// state class only; server.ts wires these into handleSlackEvent's existing
// drop points. No network calls live here — the caller posts the notice.

import { appendFileSync, chmodSync, existsSync, readFileSync, renameSync, statSync, writeFileSync } from 'node:fs';

/** Head marker of every auto-notice. noticeText writes it and shouldNotify's
 *  feedback-loop guard reads it, so the two can never drift apart. */
export const NOTICE_MARKER = '[auto-notice ·';
/** Marker used by earlier bridge builds; still recognised so a mixed fleet
 *  cannot ping-pong notices. */
export const LEGACY_NOTICE_MARKER = '[\uC790\uB3D9 \u00B7';

/** Minimal shape shouldNotify needs off a Slack message event. */
export interface DropNoticeEvent {
  bot_id?: string;
  subtype?: string;
  user?: string;
  text?: string;
  channel?: string;
  channel_type?: string;
}

export interface DropNoticeContext {
  /** Bridge bots allowed to speak to this one (ALLOWED_SLACK_BOT_USER_IDS). */
  allowedBotUserIds: Set<string>;
  /** This bridge's own resolved bot user id. */
  selfUserId: string;
  /** Same membership test server.ts already uses for gate (a). */
  isListenedChannel: (channel: string | undefined, channelType: string | undefined) => boolean;
}

/**
 * True only for the one drop worth surfacing to the channel: a peer bot,
 * NOT on the allowlist, explicitly mentioning us, in a channel we listen to
 * (or a thread of it — same `channel` field either way), not a DM, not our
 * own echo, and not itself an auto-notice (feedback-loop guard).
 */
export function shouldNotify(ev: DropNoticeEvent, ctx: DropNoticeContext): boolean {
  const fromBot = Boolean(ev.bot_id) || ev.subtype === 'bot_message';
  if (!fromBot) return false;
  if (!ev.user || ctx.allowedBotUserIds.has(ev.user)) return false;
  const text = ev.text ?? '';
  if (!text.includes(`<@${ctx.selfUserId}>`)) return false;
  if (!ctx.isListenedChannel(ev.channel, ev.channel_type)) return false;
  if (ev.user === ctx.selfUserId) return false;
  if (ev.channel_type === 'im') return false;
  const head = text.trim();
  if (head.startsWith(NOTICE_MARKER) || head.startsWith(LEGACY_NOTICE_MARKER)) return false;
  return true;
}

/** Notice text posted into the same thread the dropped message was in. */
export function noticeText(sender: string, botName: string): string {
  return `<@${sender}> ${NOTICE_MARKER} ${botName} bridge] your message was not delivered: you are not on my bot allowlist (ALLOWED_SLACK_BOT_USER_IDS).`;
}

interface DropNotifierState {
  /** `${sender}|${channel}` -> last-notified epoch ms. */
  pairs: Record<string, number>;
  /** Epoch ms of every notice sent in the trailing hour (pruned on read). */
  totalTimestamps: number[];
}

const PAIR_WINDOW_MS = 30 * 60 * 1000;
const TOTAL_WINDOW_MS = 60 * 60 * 1000;
const TOTAL_CAP = 10;

function emptyState(): DropNotifierState {
  return { pairs: {}, totalTimestamps: [] };
}

/**
 * Rate limit for the notice, persisted to `statePath` so a bridge restart
 * does not reset it. (sender, channel) pair: 1 notice / 30 min. All pairs
 * combined: 10 notices / 1 hour.
 */
export class DropNotifier {
  private readonly statePath: string;
  private readonly now: () => number;
  private state: DropNotifierState;

  constructor(statePath: string, now: () => number = Date.now) {
    this.statePath = statePath;
    this.now = now;
    this.state = this.load();
  }

  private load(): DropNotifierState {
    try {
      if (existsSync(this.statePath)) {
        const raw = JSON.parse(readFileSync(this.statePath, 'utf8')) as Partial<DropNotifierState>;
        return {
          pairs: raw.pairs && typeof raw.pairs === 'object' ? raw.pairs : {},
          totalTimestamps: Array.isArray(raw.totalTimestamps) ? raw.totalTimestamps : [],
        };
      }
    } catch {
      // Corrupt or unreadable state file — fail open into a fresh state
      // rather than throw; the rate limit just resets, which is safe.
    }
    return emptyState();
  }

  private persist(): void {
    try {
      writeFileSync(this.statePath, JSON.stringify(this.state), { mode: 0o600 });
      chmodSync(this.statePath, 0o600);
    } catch {
      // Best effort — a state-write failure must never block message flow.
    }
  }

  /** True if a notice for (sender, channel) may be sent right now; records it if so. */
  allow(sender: string, channel: string): boolean {
    const nowMs = this.now();
    this.state.totalTimestamps = this.state.totalTimestamps.filter((t) => nowMs - t < TOTAL_WINDOW_MS);

    const key = `${sender}|${channel}`;
    const last = this.state.pairs[key];
    if (last !== undefined && nowMs - last < PAIR_WINDOW_MS) return false;
    if (this.state.totalTimestamps.length >= TOTAL_CAP) return false;

    this.state.pairs[key] = nowMs;
    this.state.totalTimestamps.push(nowMs);
    this.persist();
    return true;
  }
}

export interface DropRecord {
  ts: string;
  reason: string;
  sender: string | undefined;
  channel: string | undefined;
  thread: string | undefined;
}

const DEFAULT_MAX_BYTES = 2 * 1024 * 1024;

/**
 * Appends one JSONL line recording a drop — no message body, ever (see
 * design doc §3). Never throws: a logging failure must not affect delivery.
 * Single-file rotation: once `path` reaches `maxBytes`, it is renamed to
 * `path + '.1'` (overwriting any previous one) before the new line is
 * appended to a fresh `path` — every listened-channel post is a drop
 * candidate here, so this is the only cap on unbounded growth.
 */
export function logDrop(path: string, rec: DropRecord, maxBytes: number = DEFAULT_MAX_BYTES): void {
  try {
    try {
      if (existsSync(path) && statSync(path).size >= maxBytes) {
        renameSync(path, `${path}.1`);
      }
    } catch {
      // Rotation is best-effort too — a stat/rename failure just means the
      // append below grows the existing file instead of rolling it.
    }
    const line = `${JSON.stringify({ ts: rec.ts, reason: rec.reason, sender: rec.sender, channel: rec.channel, thread: rec.thread })}\n`;
    appendFileSync(path, line, { mode: 0o600 });
    chmodSync(path, 0o600);
  } catch {
    // Best effort — see docstring.
  }
}
