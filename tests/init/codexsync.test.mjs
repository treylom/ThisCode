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

test('injected skill list plans and copies a real temporary skill', () => {
  const src = mkdtempSync(join(tmpdir(), 'src-'));
  const dest = mkdtempSync(join(tmpdir(), 'dst-'));
  const skills = ['tmp-skill'];
  mkdirSync(join(src, skills[0]), { recursive: true });
  writeFileSync(join(src, skills[0], 'SKILL.md'), '# temporary');

  const plan = planCodexSync(src, dest, skills);
  assert.deepEqual(plan.map(({ skill }) => skill), skills);
  assert.equal(existsSync(join(dest, skills[0])), false, 'plan must remain dry with injected skills');

  const done = applyCodexSync(src, dest, skills);
  assert.deepEqual(done, skills);
  assert.equal(readFileSync(join(dest, skills[0], 'SKILL.md'), 'utf8'), '# temporary');
  rmSync(src, { recursive: true, force: true }); rmSync(dest, { recursive: true, force: true });
});
