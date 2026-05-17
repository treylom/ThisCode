// tests/init/detect.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { detectOS, whichSync, autodiscoverVault } from '../../scripts/lib/detect.mjs';

test('detectOS returns one of the 4 known kinds', () => {
  assert.ok(['win', 'wsl', 'linux', 'mac'].includes(detectOS()));
});

test('whichSync finds node on PATH, null for nonsense', () => {
  assert.ok(whichSync('node'));
  assert.equal(whichSync('definitely-not-a-real-binary-xyz'), null);
});

test('autodiscoverVault returns null or an existing dir', () => {
  const v = autodiscoverVault({ HOME: '/nonexistent-home-xyz' });
  assert.equal(v, null);
});

test('autodiscoverVault finds Documents/Obsidian under home', () => {
  const home = mkdtempSync(join(tmpdir(), 'tc-home-'));
  mkdirSync(join(home, 'Documents', 'Obsidian'), { recursive: true });
  assert.equal(autodiscoverVault({ HOME: home }), join(home, 'Documents', 'Obsidian'));
  rmSync(home, { recursive: true, force: true });
});

test('autodiscoverVault honors CLAUDE_DISCODE_VAULT override', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tc-vault-'));
  assert.equal(autodiscoverVault({ CLAUDE_DISCODE_VAULT: dir }), dir);
  rmSync(dir, { recursive: true, force: true });
});
