// tests/init/apply.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { injectMarkerBlock, backupFile, MARK_START, MARK_END } from '../../scripts/lib/apply.mjs';

test('injects block when markers absent', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  const f = join(dir, 'CLAUDE.md');
  writeFileSync(f, '# Existing\n');
  injectMarkerBlock(f, 'RULES POINTER');
  const out = readFileSync(f, 'utf8');
  assert.ok(out.includes('# Existing'));
  assert.ok(out.includes(MARK_START) && out.includes(MARK_END));
  assert.ok(out.includes('RULES POINTER'));
  rmSync(dir, { recursive: true, force: true });
});

test('idempotent — second inject does not duplicate', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  const f = join(dir, 'CLAUDE.md');
  writeFileSync(f, '# X\n');
  injectMarkerBlock(f, 'V1');
  injectMarkerBlock(f, 'V2');
  const out = readFileSync(f, 'utf8');
  assert.equal(out.match(new RegExp(MARK_START, 'g')).length, 1);
  assert.ok(out.includes('V2') && !out.includes('V1'));
  rmSync(dir, { recursive: true, force: true });
});

test('backupFile creates .bak copy', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  const f = join(dir, 'CLAUDE.md');
  writeFileSync(f, 'orig');
  const bak = backupFile(f);
  assert.ok(existsSync(bak));
  assert.equal(readFileSync(bak, 'utf8'), 'orig');
  rmSync(dir, { recursive: true, force: true });
});
