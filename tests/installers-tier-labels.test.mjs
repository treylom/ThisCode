import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

test('healthcheck labels match the current search contract without probing host services', (t) => {
  const fixture = mkdtempSync(join(tmpdir(), 'thiscode-health-labels-'));
  t.after(() => rmSync(fixture, { recursive: true, force: true }));
  const fixtureBin = join(fixture, 'bin');
  mkdirSync(fixtureBin);
  for (const name of ['claude', 'curl']) {
    writeFileSync(join(fixtureBin, name), '#!/bin/sh\nexit 1\n', { mode: 0o755 });
  }
  writeFileSync(join(fixtureBin, 'obsidian-cli'), '#!/bin/sh\nexit 0\n', { mode: 0o755 });
  const script = fileURLToPath(new URL('../scripts/healthcheck.sh', import.meta.url));
  const result = spawnSync('/bin/bash', [script], {
    encoding: 'utf8',
    env: { ...process.env, HOME: fixture, PATH: `${fixtureBin}:/usr/bin:/bin` },
  });
  assert.ifError(result.error);
  assert.equal(result.status, 2, result.stdout + result.stderr); // Optional tools are intentionally absent.
  assert.match(result.stdout, /Phase 2 obsidian-cli \(Tier 2\)/);
  assert.match(result.stdout, /Phase 3 vault-search MCP \(Tier 3\)/);
});
