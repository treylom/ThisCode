// tests/init/codexsync.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { planCodexSync, applyCodexSync, KM_SKILLS } from '../../scripts/lib/codexsync.mjs';

test('KM_SKILLS matches bash SKILLS array (behavior parity)', () => {
  assert.deepEqual(KM_SKILLS, []);
});

test('planCodexSync is dry (no writes), lists src→dest pairs', () => {
  const src = mkdtempSync(join(tmpdir(), 'src-'));
  const skill = KM_SKILLS[0] ?? 'sample-skill';
  mkdirSync(join(src, skill), { recursive: true });
  writeFileSync(join(src, skill, 'SKILL.md'), '# k');
  const dest = mkdtempSync(join(tmpdir(), 'dst-'));
  const before = existsSync(join(dest, skill));
  const plan = planCodexSync(src, dest);
  assert.equal(before, false);
  assert.equal(existsSync(join(dest, skill)), false, 'plan must not write');
  assert.equal(plan.length, KM_SKILLS.length ? 1 : 0, 'plan lists exactly the synced skills');
  rmSync(src, { recursive: true, force: true }); rmSync(dest, { recursive: true, force: true });
});

test('applyCodexSync copies SKILL.md into dest layer', () => {
  const src = mkdtempSync(join(tmpdir(), 'src-'));
  const skill = KM_SKILLS[0] ?? 'sample-skill';
  mkdirSync(join(src, skill), { recursive: true });
  writeFileSync(join(src, skill, 'SKILL.md'), '# lite');
  const dest = mkdtempSync(join(tmpdir(), 'dst-'));
  const done = applyCodexSync(src, dest);
  if (KM_SKILLS.length) {
    assert.equal(readFileSync(join(dest, skill, 'SKILL.md'), 'utf8'), '# lite');
  } else {
    assert.deepEqual(done, [], 'empty sync list must copy nothing');
    assert.equal(existsSync(join(dest, skill)), false, 'empty sync list must not write');
  }
  rmSync(src, { recursive: true, force: true }); rmSync(dest, { recursive: true, force: true });
});
