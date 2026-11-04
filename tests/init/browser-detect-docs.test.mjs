// tests/init/browser-detect-docs.test.mjs — the docs that open websites run the browser auto-detect first
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (p) => readFileSync(join(ROOT, p), 'utf8');
const CALL = 'scripts/browser-detect.mjs';

for (const f of ['skills/create-bot/SKILL.md', 'skills/help/SKILL.md', 'commands/start.md', 'skills/slack-configure/SKILL.md']) {
  test(`${f} runs the browser auto-detect`, () => {
    assert.ok(read(f).includes(CALL), `${f} must call ${CALL}`);
  });
}

test('create-bot: auto-detect step comes before the availability-detection fallback', () => {
  const s = read('skills/create-bot/SKILL.md');
  const a = s.indexOf(CALL);
  const b = s.indexOf('**전제 — 가용성 탐지**');
  assert.ok(a > 0 && b > 0 && a < b, 'detector call must precede the fallback paragraph');
  for (const k of ['provider=ego', 'provider=aside', 'provider=fallback']) assert.ok(s.includes(k), k);
});

test('create-bot: an ego lite user-control stop is not a fail-over', () => {
  const s = read('skills/create-bot/SKILL.md');
  for (const k of ['다음 칸으로 넘어가지 않는다', 'takeOverTaskSpace', 'Need your action', 'Return to agent']) assert.ok(s.includes(k), k);
  assert.ok(s.indexOf('다음 칸으로 넘어가지 않는다') > s.indexOf('실행 중 실패하면'), 'exception follows the fail-over line');
});

test('plugin.json and marketplace.json carry the same version', () => {
  const p = JSON.parse(read('.claude-plugin/plugin.json')).version;
  const m = JSON.parse(read('.claude-plugin/marketplace.json')).plugins.find((x) => x.name === 'thiscode').version;
  assert.equal(p, m);
});
