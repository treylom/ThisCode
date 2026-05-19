import { test } from 'node:test';
import assert from 'node:assert/strict';
import { setupFlowAliases, setupFlowGuide } from '../../scripts/lib/setup-flow.mjs';

test('setup flow aliases are repo and BOT_WD parameterized', () => {
  const text = setupFlowAliases({
    product: 'thiscode',
    repoRoot: '/repo/ThisCode',
    botWd: '/bots/reviewer',
    stateDir: '/state/discord-reviewer',
    session: 'thiscode',
  });
  assert.match(text, /cd '\/repo\/ThisCode'/);
  assert.match(text, /BOT_WD='\/bots\/reviewer'/);
  assert.match(text, /thiscode-discord/);
  assert.match(text, /thiscode-yolo-on/);
  assert.doesNotMatch(text, /cmux/i);
});

test('setup flow guide is tmux-only and includes progress cadence', () => {
  const text = setupFlowGuide('thiscode');
  assert.match(text, /tmux/i);
  assert.match(text, /Discord/i);
  assert.match(text, /progress_report_cadence/);
  assert.match(text, /danger-full-access|YOLO/i);
  assert.doesNotMatch(text, /cmux/i);
});
