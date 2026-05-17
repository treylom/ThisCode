// tests/init/questions.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SCRIPT, nextQuestion, isInScope } from '../../scripts/lib/questions.mjs';

test('SCRIPT covers every spec §6.A id, in order', () => {
  const ids = SCRIPT.map(q => q.id);
  for (const id of ['tone','os_confirm','wsl_recommend','harness','codex_auth','codex_skill_layer',
    'codex_marketplace','codex_config','vault','bot_topology','bot_detail','daemon_guide',
    'codex_runner','codex_launch_compat','codex_yolo','apply_confirm']) {
    assert.ok(ids.includes(id), `missing question: ${id}`);
  }
});
test('Q2 wsl_recommend only in scope on Windows native', () => {
  const q = SCRIPT.find(q => q.id === 'wsl_recommend');
  assert.equal(isInScope(q, { os: 'win', answers: {} }), true);
  assert.equal(isInScope(q, { os: 'mac', answers: {} }), false);
});
test('Q3c codex_auth only when harness includes codex', () => {
  const q = SCRIPT.find(q => q.id === 'codex_auth');
  assert.equal(isInScope(q, { os: 'mac', answers: { harness: 'claude' } }), false);
  assert.equal(isInScope(q, { os: 'mac', answers: { harness: 'both' } }), true);
});
test('nextQuestion skips answered + out-of-scope', () => {
  const ctx = { os: 'mac', answers: { tone: 'plain' } };
  const n = nextQuestion(ctx, ['tone']);
  assert.equal(n.id, 'os_confirm');
});
test('nextQuestion null when all in-scope answered', () => {
  const ctx = { os: 'mac', answers: { harness: 'claude', bot_topology: 'single', daemon_guide: 'no' } };
  const answered = SCRIPT.filter(q => isInScope(q, ctx)).map(q => q.id);
  assert.equal(nextQuestion(ctx, answered), null);
});
