// tests/init/codexsync.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { planCodexSync, applyCodexSync, KM_SKILLS } from '../../scripts/lib/codexsync.mjs';

test('KM_SKILLS matches bash SKILLS array (behavior parity)', () => {
  assert.deepEqual(KM_SKILLS, ['knowledge-manager','knowledge-manager-lite',
    'knowledge-manager-plain','knowledge-manager-at','knowledge-manager-bootstrap']);
});

test('planCodexSync is dry (no writes), lists src→dest pairs', () => {
  const src = mkdtempSync(join(tmpdir(), 'src-'));
  mkdirSync(join(src, 'knowledge-manager-plain'), { recursive: true });
  writeFileSync(join(src, 'knowledge-manager-plain', 'SKILL.md'), '# k');
  const dest = mkdtempSync(join(tmpdir(), 'dst-'));
  const before = existsSync(join(dest, 'knowledge-manager-plain'));
  const plan = planCodexSync(src, dest);
  assert.equal(before, false);
  assert.equal(existsSync(join(dest, 'knowledge-manager-plain')), false, 'plan must not write');
  assert.ok(plan.some(p => p.skill === 'knowledge-manager-plain'));
  rmSync(src, { recursive: true, force: true }); rmSync(dest, { recursive: true, force: true });
});

test('applyCodexSync copies SKILL.md into dest layer', () => {
  const src = mkdtempSync(join(tmpdir(), 'src-'));
  mkdirSync(join(src, 'knowledge-manager-lite'), { recursive: true });
  writeFileSync(join(src, 'knowledge-manager-lite', 'SKILL.md'), '# lite');
  const dest = mkdtempSync(join(tmpdir(), 'dst-'));
  applyCodexSync(src, dest);
  assert.equal(readFileSync(join(dest, 'knowledge-manager-lite', 'SKILL.md'), 'utf8'), '# lite');
  rmSync(src, { recursive: true, force: true }); rmSync(dest, { recursive: true, force: true });
});
