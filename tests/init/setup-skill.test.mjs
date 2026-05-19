import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('setup skill is generated through prompt-skill discipline', () => {
  const text = readFileSync('skills/setup/SKILL.md', 'utf8');
  assert.match(text, /^---\nname: setup\n/m);
  assert.match(text, /\/prompt --batch GPT-5\.5 상세/);
  assert.match(text, /thiscode setup|thiscode init/i);
  assert.match(text, /progress_report_cadence/);
  assert.match(text, /tmux/i);
  assert.match(text, /Do not use cmux/i);
});
