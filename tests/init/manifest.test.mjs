import { test } from 'node:test';
import assert from 'node:assert/strict';
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
