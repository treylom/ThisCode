// tests/init/detect.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
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
