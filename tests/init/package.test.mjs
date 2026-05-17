// tests/init/package.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const pkg = JSON.parse(readFileSync(new URL('../../package.json', import.meta.url)));

test('bin is the Node entry, not a .sh', () => {
  assert.equal(pkg.bin.thiscode, 'bin/thiscode.mjs');
  assert.ok(!('thiscode-km-version' in pkg.bin) || pkg.bin['thiscode-km-version'].endsWith('.mjs'),
    'no .sh bin allowed (Windows-fatal)');
});

test('contributors include Codex', () => {
  const blob = JSON.stringify(pkg.contributors || []);
  assert.match(blob, /Codex/i);
});

test('test script uses node --test', () => {
  assert.equal(pkg.scripts.test, 'node scripts/run-tests.mjs');
});

test('bin/ shipped in files[]', () => {
  assert.ok(pkg.files.includes('bin/'));
});
