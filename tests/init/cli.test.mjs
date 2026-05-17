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

test('non-TTY --check exits 0 without hanging (no readline)', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  // stdin piped + immediately closed = non-TTY, no input available
  const out = execFileSync(process.execPath, [BIN, '--check'], {
    cwd: dir, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], input: '',
  });
  assert.match(out, /점검만|check/i);
  rmSync(dir, { recursive: true, force: true });
});

test('non-TTY --apply without --yes errors friendly (exit 2), does not hang', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  let code = 0, stderr = '';
  try {
    execFileSync(process.execPath, [BIN, '--apply'], {
      cwd: dir, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], input: '',
    });
  } catch (e) { code = e.status; stderr = String(e.stderr || ''); }
  assert.equal(code, 2);
  assert.match(stderr, /--yes|미리보기|check/);
  rmSync(dir, { recursive: true, force: true });
});

test('--check prints step reasons (friendly, plain) and WSL note shape exists', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  const out = execFileSync(process.execPath, [BIN, '--check'], { cwd: dir, encoding: 'utf8', stdio: ['pipe','pipe','pipe'], input: '' });
  assert.match(out, /확인해요|이유|왜/);          // reason text emitted (friendly)
  assert.match(out, /점검만|check/i);
  rmSync(dir, { recursive: true, force: true });
});
