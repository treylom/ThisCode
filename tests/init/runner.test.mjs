// tests/init/runner.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { runnerFile } from '../../scripts/lib/runner.mjs';

test('mac → launchd plist', () => {
  const r = runnerFile('mac', { label: 'com.x.bot', cmd: 'node bot.mjs' });
  assert.match(r.filename, /\.plist$/);
  assert.match(r.content, /<plist/);
  assert.match(r.content, /com\.x\.bot/);
});

test('linux → systemd user unit', () => {
  const r = runnerFile('linux', { label: 'xbot', cmd: 'node bot.mjs' });
  assert.match(r.filename, /\.service$/);
  assert.match(r.content, /\[Service\]/);
});

test('win → tmux/manual fallback note (no plist/systemd)', () => {
  const r = runnerFile('win', { label: 'xbot', cmd: 'node bot.mjs' });
  assert.match(r.content, /WSL|manual|tmux/i);
});

test('no auto-start — content is a file, function never spawns', () => {
  const r = runnerFile('mac', { label: 'l', cmd: 'c' });
  assert.equal(typeof r.content, 'string');
  assert.ok(!('pid' in r));
});
