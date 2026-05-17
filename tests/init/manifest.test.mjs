import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, rmSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { loadManifest, validateStep } from '../../scripts/lib/manifest.mjs';

test('loadManifest returns ordered steps from install/thiscode.install.json', () => {
  const steps = loadManifest();
  assert.ok(Array.isArray(steps) && steps.length > 0);
  for (let i = 1; i < steps.length; i++) assert.ok(steps[i].order >= steps[i - 1].order, 'sorted by order');
  for (const s of steps) assert.equal(validateStep(s), true, `valid: ${s.id}`);
});

test('validateStep rejects missing required field', () => {
  assert.equal(validateStep({ id: 'x', order: 1, action: 'detect' }), false); // no reason/verify
  // D1: on_fail.next_command is required (cross-repo schema parity with ThisCodex strict validator)
  assert.equal(validateStep({ id: 'x', order: 1, when: 'always', action: 'detect', reason: 'r', safety: 'none', verify: { type: 'detected' } }), false); // no on_fail
  assert.equal(validateStep({ id: 'x', order: 1, when: 'always', action: 'detect', reason: 'r', safety: 'none', verify: { type: 'detected' }, on_fail: { next_command: 'node bin/thiscode.mjs --check' } }), true);
});

test('loadManifest sorts steps by order', () => {
  const tmpDir = mkdtempSync(join(tmpdir(), 'thiscode-sort-test-'));
  const tmpPath = join(tmpDir, 'test-manifest.json');
  const outOfOrder = {
    version: 1,
    steps: [
      { id: 'four', order: 80, when: 'always', action: 'apply', reason: 'r', safety: 'none', verify: { type: 'marker-present', key: 'x' }, on_fail: { next_command: 'cmd' } },
      { id: 'two', order: 40, when: 'always', action: 'prompt', reason: 'r', safety: 'none', verify: { type: 'answered', key: 'x' }, on_fail: { next_command: 'cmd' } },
      { id: 'three', order: 20, when: 'always', action: 'guide', reason: 'r', safety: 'none', verify: { type: 'ack', key: 'x' }, on_fail: { next_command: 'cmd' } },
      { id: 'one', order: 10, when: 'always', action: 'detect', reason: 'r', safety: 'none', verify: { type: 'detected', key: 'x' }, on_fail: { next_command: 'cmd' } }
    ]
  };
  writeFileSync(tmpPath, JSON.stringify(outOfOrder), 'utf8');
  const steps = loadManifest(tmpPath);
  assert.deepEqual(steps.map(s => s.order), [10, 20, 40, 80], 'steps sorted by order');
  rmSync(tmpDir, { recursive: true, force: true });
});
