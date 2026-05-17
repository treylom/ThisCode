// tests/init/state.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { loadState, saveState, mergeAnswer, resumeSummary } from '../../scripts/lib/state.mjs';

test('loadState returns fresh skeleton when no file', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  const s = loadState(dir);
  assert.equal(s.version, 1);
  assert.equal(s.completed_steps.length, 0);
  rmSync(dir, { recursive: true, force: true });
});
test('mergeAnswer records step + answer, saveState round-trips', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  let s = loadState(dir);
  s = mergeAnswer(s, 'bot_topology', 'multi_planned');
  saveState(dir, s);
  const r = loadState(dir);
  assert.equal(r.answers.bot_topology, 'multi_planned');
  assert.ok(r.completed_steps.includes('bot_topology'));
  rmSync(dir, { recursive: true, force: true });
});
test('resumeSummary lists prior choices, omits unanswered', () => {
  let s = mergeAnswer(loadState('/tmp'), 'tone', 'plain');
  const sum = resumeSummary(s);
  assert.match(sum, /tone/);
  assert.doesNotMatch(sum, /bot_topology/);
});
