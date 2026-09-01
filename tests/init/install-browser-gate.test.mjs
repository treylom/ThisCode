import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const GATE = join(REPO, 'scripts', 'install-browser-gate.sh');
const COMMAND = join(REPO, 'commands', 'install-browser.md');
const CARDS = join(REPO, 'docs', 'install-browser-manual-cards.md');

test('browser gate isolated replay passes 0~4 and rejects a broken MCP command', () => {
  const r = spawnSync('bash', [GATE, '--self-test'], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /\[SELFTEST\] 6\/6 passed/);
});

test('student command has one machine gate per step in 0→4 order', () => {
  const text = readFileSync(COMMAND, 'utf8');
  const steps = [...text.matchAll(/install-browser-gate\.sh" ([0-4])/g)].map((m) => Number(m[1]));
  assert.deepEqual(steps, [0, 1, 2, 3, 4]);
  assert.match(text, /n단계 실패 → 수동 카드 X/);
});

test('manual fallback keeps the A~E recovery boundary', () => {
  const text = readFileSync(CARDS, 'utf8');
  const cards = [...text.matchAll(/^## 카드 ([A-E]) —/gm)].map((m) => m[1]);
  assert.deepEqual(cards, ['A', 'B', 'C', 'D', 'E']);
  assert.match(text, /-s project/);
});
