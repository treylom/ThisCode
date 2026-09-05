import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const posixOnlySkip = process.platform === 'win32'
  ? 'POSIX shell fixtures; exercised by macOS and Ubuntu jobs'
  : false;

test('healthcheck labels match the current search contract without probing host services', { skip: posixOnlySkip }, (t) => {
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
  assert.match(result.stdout, /Phase 2 obsidian-cli \(local tool\)/);
  assert.match(result.stdout, /Phase 3 vault-search MCP \(local embedding\)/);
});

test('missing Obsidian keeps MCP ahead of ripgrep in both fallback notices', { skip: posixOnlySkip }, (t) => {
  const fixture = mkdtempSync(join(tmpdir(), 'thiscode-missing-obsidian-'));
  t.after(() => rmSync(fixture, { recursive: true, force: true }));
  const fixtureBin = join(fixture, 'bin');
  mkdirSync(fixtureBin);
  // Avoid detecting any host GUI installation; CLI candidates are excluded by PATH.
  writeFileSync(join(fixtureBin, 'uname'), '#!/bin/sh\nprintf "FixtureOS\\n"\n', { mode: 0o755 });
  const script = fileURLToPath(new URL('../scripts/install-obsidian-cli.sh', import.meta.url));
  for (const args of [['--check'], []]) {
    const result = spawnSync('/bin/bash', [script, ...args], {
      encoding: 'utf8', input: 'n\n',
      env: { ...process.env, HOME: fixture, PATH: `${fixtureBin}:/usr/bin:/bin` },
    });
    assert.ifError(result.error);
    assert.equal(result.status, args.length ? 1 : 0, result.stdout + result.stderr);
    assert.match(result.stdout, /Tier 3 \(Obsidian MCP\), then Tier 4 \(text search\) remain as km fallbacks/);
  }
});
