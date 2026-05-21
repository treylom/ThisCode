import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const LABELS = [
  'SOURCE FACT',
  'DERIVED INFERENCE',
  'UNCERTAINTY',
  'DELEGATED TASK',
];

const SOUL_TEMPLATES = [
  'templates/soul-custom.md',
  'templates/soul-general-assistant.md',
  'templates/soul-research-bot.md',
  'templates/soul-schedule-bot.md',
  'templates/soul-writing-bot.md',
];

test('all soul templates hard-code the 4-way self-check labels', () => {
  for (const file of SOUL_TEMPLATES) {
    const body = readFileSync(file, 'utf8');
    assert.match(body, /4-way/i, `${file} should name the 4-way report rule`);
    for (const label of LABELS) {
      assert.match(body, new RegExp(label), `${file} should include ${label}`);
    }
  }
});
