import { test } from 'node:test';
import assert from 'node:assert/strict';
import { setupFlowAliases, setupFlowGuide } from '../../scripts/lib/setup-flow.mjs';
import { installBotLauncher } from '../../scripts/lib/bot-launcher.mjs';

test('setup aliases invoke the existing bot launcher output, not an unshipped repo script', () => {
  const cfg = {
    channel: 'discord', aliasName: 'reviewer', sessionName: 'reviewer',
    botWd: '/bots/reviewer', stateDir: '/state/reviewer',
  };
  const preview = installBotLauncher(cfg);
  const text = setupFlowAliases({ product: 'thiscode', repoRoot: '/repo/ThisCode', ...cfg });
  assert.ok(text.includes(preview.launcherPath));
  assert.doesNotMatch(text, /\.\/scripts\/launch\.sh/);
  assert.match(text, /\.thiscode-bot-launcher\.sh.*start/);
});

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

test('setup flow aliases export heartbeat env from selected progress cadence', () => {
  const text = setupFlowAliases({
    product: 'thiscode',
    repoRoot: '/repo/ThisCode',
    botWd: '/bots/reviewer',
    stateDir: '/state/discord-reviewer',
    session: 'thiscode',
    progressReportCadence: '5m',
  });
  assert.match(text, /THISCODE_PROGRESS_CADENCE='5m'/);
  assert.match(text, /THISCODE_HEARTBEAT_SEC='300'/);
});

test('setup flow guide is tmux-only and includes progress cadence', () => {
  const text = setupFlowGuide('thiscode');
  assert.match(text, /tmux/i);
  assert.match(text, /Discord/i);
  assert.match(text, /progress_report_cadence/);
  assert.match(text, /danger-full-access|YOLO/i);
  assert.doesNotMatch(text, /cmux/i);
});
