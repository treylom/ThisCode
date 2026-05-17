// tests/init/recommend.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { recommendPhases } from '../../scripts/lib/recommend.mjs';

test('no python → graphrag deferred', () => {
  const r = recommendPhases({ note_count: 1500, python: false, obsidian_cli: true });
  assert.ok(r.later.includes('phase-4-graphrag-no-python'));
});

test('1000+ notes → graphrag strong', () => {
  const r = recommendPhases({ note_count: 1200, python: true, obsidian_cli: true });
  assert.ok(r.recommended.includes('phase-4-graphrag-strong'));
});

test('<500 notes → graphrag optional (later)', () => {
  const r = recommendPhases({ note_count: 200, python: true, obsidian_cli: false });
  assert.ok(r.later.includes('phase-4-graphrag-optional'));
  assert.ok(r.recommended.includes('phase-2-cli-install'));
});

test('phase-0/1 always current; phase-7 always later', () => {
  const r = recommendPhases({ note_count: 0, python: false, obsidian_cli: false });
  assert.ok(r.current.includes('phase-0-obsidian') && r.current.includes('phase-1-ripgrep'));
  assert.ok(r.later.includes('phase-7-hybrid-search'));
});
