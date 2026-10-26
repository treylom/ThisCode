import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DropNotifier, LEGACY_NOTICE_MARKER, NOTICE_MARKER, logDrop, noticeText, shouldNotify } from '../dist/drop-notice.js';

const SELF = 'U_SELF';
const PEER = 'U_PEER';
const CHANNEL = 'C1';

function baseEvent() {
  return {
    bot_id: 'B123',
    subtype: 'bot_message',
    user: PEER,
    text: `hello <@${SELF}> how are you`,
    channel: CHANNEL,
    channel_type: 'channel',
  };
}

function baseCtx(overrides = {}) {
  return {
    allowedBotUserIds: new Set(),
    selfUserId: SELF,
    isListenedChannel: () => true,
    ...overrides,
  };
}

test('shouldNotify: all conditions true -> true', () => {
  assert.equal(shouldNotify(baseEvent(), baseCtx()), true);
});

test('shouldNotify: not a bot -> false', () => {
  const ev = { ...baseEvent(), bot_id: undefined, subtype: undefined };
  assert.equal(shouldNotify(ev, baseCtx()), false);
});

test('shouldNotify: sender already allowed -> false', () => {
  const ctx = baseCtx({ allowedBotUserIds: new Set([PEER]) });
  assert.equal(shouldNotify(baseEvent(), ctx), false);
});

test('shouldNotify: no mention of self -> false', () => {
  const ev = { ...baseEvent(), text: 'hello there, no mention' };
  assert.equal(shouldNotify(ev, baseCtx()), false);
});

test('shouldNotify: not a listened channel -> false', () => {
  const ctx = baseCtx({ isListenedChannel: () => false });
  assert.equal(shouldNotify(baseEvent(), ctx), false);
});

test('shouldNotify: sender is self (echo) -> false', () => {
  const ev = { ...baseEvent(), user: SELF, text: `hi <@${SELF}>` };
  assert.equal(shouldNotify(ev, baseCtx()), false);
});

test('shouldNotify: DM -> false', () => {
  const ev = { ...baseEvent(), channel_type: 'im' };
  assert.equal(shouldNotify(ev, baseCtx()), false);
});

test('shouldNotify: text is itself an auto-notice -> false', () => {
  const ev = { ...baseEvent(), text: `${NOTICE_MARKER} peer-bot bridge] <@${SELF}> already told you` };
  assert.equal(shouldNotify(ev, baseCtx()), false);
});

test('shouldNotify: notice from an earlier bridge build (legacy marker) -> false', () => {
  const ev = { ...baseEvent(), text: `${LEGACY_NOTICE_MARKER} peer-bot] <@${SELF}> already told you` };
  assert.equal(shouldNotify(ev, baseCtx()), false);
});

test('noticeText: output starts the loop guard marker (text and guard share one constant)', () => {
  const ev = { ...baseEvent(), text: noticeText(SELF, 'peer-bot').replace(`<@${SELF}> `, '') + ` <@${SELF}>` };
  assert.equal(shouldNotify(ev, baseCtx()), false);
});

test('noticeText: exact template', () => {
  assert.equal(
    noticeText('U_PEER', 'peer-bot'),
    '<@U_PEER> [auto-notice · peer-bot bridge] your message was not delivered: you are not on my bot allowlist (ALLOWED_SLACK_BOT_USER_IDS).',
  );
});

test('DropNotifier: same (sender, channel) pair twice within 30 min -> second is false', () => {
  const dir = mkdtempSync(join(tmpdir(), 'drop-notice-test-'));
  const statePath = join(dir, 'state.json');
  let clock = 1_000_000;
  const now = () => clock;
  const notifier = new DropNotifier(statePath, now);
  assert.equal(notifier.allow(PEER, CHANNEL), true);
  clock += 5 * 60 * 1000; // +5min, still inside 30min window
  assert.equal(notifier.allow(PEER, CHANNEL), false);
  rmSync(dir, { recursive: true, force: true });
});

test('DropNotifier: same pair after 30 min -> true again', () => {
  const dir = mkdtempSync(join(tmpdir(), 'drop-notice-test-'));
  const statePath = join(dir, 'state.json');
  let clock = 1_000_000;
  const now = () => clock;
  const notifier = new DropNotifier(statePath, now);
  assert.equal(notifier.allow(PEER, CHANNEL), true);
  clock += 30 * 60 * 1000 + 1; // just past 30min
  assert.equal(notifier.allow(PEER, CHANNEL), true);
  rmSync(dir, { recursive: true, force: true });
});

test('DropNotifier: 11th notice overall within 1h -> false', () => {
  const dir = mkdtempSync(join(tmpdir(), 'drop-notice-test-'));
  const statePath = join(dir, 'state.json');
  let clock = 1_000_000;
  const now = () => clock;
  const notifier = new DropNotifier(statePath, now);
  for (let i = 0; i < 10; i += 1) {
    // Distinct (sender, channel) pairs so the per-pair cap never blocks — the
    // total cap is what's under test.
    assert.equal(notifier.allow(`U_PEER_${i}`, CHANNEL), true);
    clock += 1000;
  }
  assert.equal(notifier.allow('U_PEER_10', CHANNEL), false);
  rmSync(dir, { recursive: true, force: true });
});

test('DropNotifier: a new instance reading the same state file keeps the limit', () => {
  const dir = mkdtempSync(join(tmpdir(), 'drop-notice-test-'));
  const statePath = join(dir, 'state.json');
  let clock = 1_000_000;
  const now = () => clock;
  const first = new DropNotifier(statePath, now);
  assert.equal(first.allow(PEER, CHANNEL), true);

  const second = new DropNotifier(statePath, now);
  assert.equal(second.allow(PEER, CHANNEL), false); // still inside 30min, persisted state honored
  rmSync(dir, { recursive: true, force: true });
});

test('logDrop: appends one JSON line with no body field, mode 0600', () => {
  const dir = mkdtempSync(join(tmpdir(), 'drop-notice-test-'));
  const path = join(dir, 'drops.jsonl');
  logDrop(path, { ts: '2026-09-26T00:00:00.000Z', reason: 'bot-not-allowed', sender: PEER, channel: CHANNEL, thread: undefined });

  const raw = readFileSync(path, 'utf8');
  const lines = raw.split('\n').filter(Boolean);
  assert.equal(lines.length, 1);
  const rec = JSON.parse(lines[0]);
  assert.equal(rec.reason, 'bot-not-allowed');
  assert.equal(rec.sender, PEER);
  assert.equal(rec.channel, CHANNEL);
  assert.ok(!('text' in rec));
  assert.ok(!('content' in rec));

  const mode = statSync(path).mode & 0o777;
  assert.equal(mode, 0o600);
  rmSync(dir, { recursive: true, force: true });
});

test('logDrop: rotates path -> path.1 once maxBytes is reached, keeps path small', () => {
  const dir = mkdtempSync(join(tmpdir(), 'drop-notice-test-'));
  const path = join(dir, 'drops.jsonl');
  const maxBytes = 200;
  const rec = { ts: '2026-09-26T00:00:00.000Z', reason: 'not-listened-channel', sender: PEER, channel: CHANNEL, thread: undefined };
  const lineLen = `${JSON.stringify(rec)}\n`.length;

  for (let i = 0; i < 20; i += 1) {
    logDrop(path, rec, maxBytes);
  }

  assert.ok(existsSync(join(dir, 'drops.jsonl.1')));
  const finalSize = statSync(path).size;
  assert.ok(finalSize < maxBytes + lineLen, `expected ${finalSize} < ${maxBytes + lineLen}`);
  rmSync(dir, { recursive: true, force: true });
});

test('logDrop: an existing .1 is overwritten by the next rotation, not appended to', () => {
  const dir = mkdtempSync(join(tmpdir(), 'drop-notice-test-'));
  const path = join(dir, 'drops.jsonl');
  const rotatedPath = `${path}.1`;
  const maxBytes = 200;
  const recA = { ts: '2026-09-26T00:00:00.000Z', reason: 'not-listened-channel', sender: PEER, channel: CHANNEL, thread: undefined };
  const recB = { ts: '2026-09-26T01:00:00.000Z', reason: 'bot-no-mention', sender: 'U_OTHER', channel: 'C9', thread: undefined };

  for (let i = 0; i < 20; i += 1) logDrop(path, recA, maxBytes);
  const firstRotatedContent = readFileSync(rotatedPath, 'utf8');

  for (let i = 0; i < 20; i += 1) logDrop(path, recB, maxBytes);
  const secondRotatedContent = readFileSync(rotatedPath, 'utf8');

  assert.notEqual(secondRotatedContent, firstRotatedContent);
  assert.ok(secondRotatedContent.includes('bot-no-mention'));
  assert.ok(!secondRotatedContent.includes('not-listened-channel'));
  rmSync(dir, { recursive: true, force: true });
});
