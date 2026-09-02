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

test('browser gate replays 0~4 and fails closed for isolated step 4', () => {
  const r = spawnSync('bash', [GATE, '--self-test'], { encoding: 'utf8' });
  assert.equal(r.status, 0, [r.stdout, r.stderr].filter(Boolean).join('\n'));
  assert.match(r.stdout, /\[SELFTEST\] 23\/23 passed/);
});

test('browser gate uses Node for config diff and has no Python runtime dependency', () => {
  const text = readFileSync(GATE, 'utf8');
  assert.doesNotMatch(text, /\bpython3\b/);
  assert.match(text, /node - "\$before_file" "\$after_file"/);
});

test('isolated verification never copies Claude credentials', () => {
  const text = readFileSync(GATE, 'utf8');
  assert.doesNotMatch(text, /cp[^\n]*\.credentials\.json/);
  assert.match(text, /4단계 검증 불가\(인증 미승계\)/);
});

test('student command has one machine gate per step in 0→4 order', () => {
  const text = readFileSync(COMMAND, 'utf8');
  const steps = [...text.matchAll(/install-browser-gate\.sh" ([0-4])/g)].map((m) => Number(m[1]));
  assert.deepEqual(steps, [0, 1, 2, 3, 4]);
  assert.match(text, /n단계 실패 → 수동 카드 X/);
  assert.match(text, /프로젝트 Playwright 연결 승인 상태까지 확인했습니다/);
  assert.match(text, /승인 대기 상태면 자동으로 우회하지 않고/);
});

test('manual fallback keeps the A~E recovery boundary', () => {
  const text = readFileSync(CARDS, 'utf8');
  const cards = [...text.matchAll(/^## 카드 ([A-E]) —/gm)].map((m) => m[1]);
  assert.deepEqual(cards, ['A', 'B', 'C', 'D', 'E']);
  assert.match(text, /-s project/);
  assert.match(text, /4b 승인 상태 확인: 프로젝트 Playwright 연결 승인됨/);
  assert.match(text, /\/thiscode:install-browser`를 다시 실행/);
  assert.match(text, /Playwright 연결을 한 곳만 남긴 뒤/);
});

test('automatic completion and card E share the approval-state sentence', () => {
  const command = readFileSync(COMMAND, 'utf8');
  const cards = readFileSync(CARDS, 'utf8');
  const sentence = '브라우저 준비가 끝났습니다. 프로젝트 Playwright 연결 승인 상태까지 확인했습니다. 이 프로젝트에서 웹페이지 열기와 화면 읽기를 사용할 수 있습니다.';
  assert.equal(command.includes(sentence), true);
  assert.equal(cards.includes(sentence), true);
});
