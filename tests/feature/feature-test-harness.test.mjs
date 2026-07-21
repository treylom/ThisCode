import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const HARNESS = join(ROOT, 'scripts', 'feature-test.mjs');

function run(args) {
  const r = spawnSync(process.execPath, [HARNESS, ...args], { encoding: 'utf8' });
  return { code: r.status, out: (r.stdout || '') + (r.stderr || '') };
}

test('feature-test harness file is shipped', () => {
  assert.ok(existsSync(HARNESS), 'scripts/feature-test.mjs missing');
});

test('no-arg = sweep of all features EXCEPT graphrag-bench, exit 0', () => {
  const { code, out } = run([]);
  assert.equal(code, 0, `expected exit 0, got ${code}\n${out}`);
  assert.match(out, /sweep \(8 features\)/);
  for (const id of ['memory', 'tmux', 'discord-gate', 'graphrag', 'meeting', 'rules', 'hooks', 'install']) {
    assert.match(out, new RegExp(`\\b${id}\\b`), `sweep missing ${id}`);
  }
  assert.doesNotMatch(out, /\bgraphrag-bench\b/, 'default sweep must EXCLUDE graphrag-bench');
});

test('graphrag-bench is separately runnable', () => {
  const { code, out } = run(['graphrag-bench']);
  assert.equal(code, 0, out);
  assert.match(out, /one \(1 feature\)/);
  assert.match(out, /graphrag-bench/);
});

test('all / --bench includes graphrag-bench', () => {
  const { code, out } = run(['all']);
  assert.equal(code, 0, out);
  assert.match(out, /all \(9 features\)/);
  assert.match(out, /graphrag-bench/);
});

test('natural-language arg fuzzy-matches one feature', () => {
  const ko = run(['메모리']);
  assert.equal(ko.code, 0, ko.out);
  assert.match(ko.out, /one \(1 feature\)/);
  assert.match(ko.out, /\bmemory\b/);

  const en = run(['check', 'the', 'meeting', 'protocol']);
  assert.equal(en.code, 0, en.out);
  assert.match(en.out, /\bmeeting\b/);
});

test('unknown arg → exit 2 and lists known feature ids', () => {
  const { code, out } = run(['definitelynotafeature']);
  assert.equal(code, 2, `expected exit 2, got ${code}\n${out}`);
  assert.match(out, /no feature matched/);
  assert.match(out, /memory, tmux, discord-gate, graphrag/);
});

test('multi-run determinism: two sweeps produce identical stdout (test code must be stable)', () => {
  const a = spawnSync(process.execPath, [HARNESS], { encoding: 'utf8' });
  const b = spawnSync(process.execPath, [HARNESS], { encoding: 'utf8' });
  assert.equal(a.status, 0);
  assert.equal(b.status, 0);
  assert.equal(a.stdout, b.stdout, 'sweep output is not deterministic across runs');
});
