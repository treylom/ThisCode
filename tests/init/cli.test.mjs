// tests/init/cli.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, readdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const BIN = fileURLToPath(new URL('../../bin/thiscode.mjs', import.meta.url));
const run = (args, cwd) => execFileSync(process.execPath, [BIN, ...args], { cwd, encoding: 'utf8' });

test('--check --non-interactive writes nothing, exits 0', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  const before = readdirSync(dir).length;
  const out = run(['--check', '--non-interactive'], dir);
  assert.equal(readdirSync(dir).length, before, 'no files created in --check');
  assert.match(out, /점검만|check/i);
  rmSync(dir, { recursive: true, force: true });
});

test('--apply --non-interactive creates state file + injects', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  run(['--apply', '--non-interactive'], dir);
  assert.ok(readdirSync(dir).includes('.thiscode-init-state.json'));
  rmSync(dir, { recursive: true, force: true });
});

test('--apply backs up a pre-existing CLAUDE.md before mutating it', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  writeFileSync(join(dir, 'CLAUDE.md'), '# pre-existing user content\n');
  run(['--apply', '--non-interactive'], dir);
  const entries = readdirSync(dir);
  assert.ok(entries.includes('CLAUDE.md.thiscode.bak'), 'backup .thiscode.bak created before write');
  rmSync(dir, { recursive: true, force: true });
});

test('--tone=dev switches register', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  const out = run(['--check', '--non-interactive', '--tone=dev'], dir);
  assert.match(out, /무변경 진단|register/i);
  rmSync(dir, { recursive: true, force: true });
});
