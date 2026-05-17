import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
const BIN = fileURLToPath(new URL('../../bin/thiscode.mjs', import.meta.url));

test('thiscode doctor runs verify replay, prints per-step status, exits 0 on clean env', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-'));
  const out = execFileSync(process.execPath, [BIN, 'doctor'], { cwd: dir, encoding: 'utf8', stdio:['pipe','pipe','pipe'], input:'' });
  assert.match(out, /doctor|진단|검사/i);
  assert.match(out, /detect_env/);   // reports the verify-step ids
  rmSync(dir, { recursive: true, force: true });
});
