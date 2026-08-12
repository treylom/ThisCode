import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  chmodSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import {
  installBotLauncher,
  launcherScript,
} from '../../scripts/lib/bot-launcher.mjs';

function fixture(channel = 'discord') {
  const root = mkdtempSync(join(tmpdir(), 'thiscode-launcher-'));
  const botWd = join(root, 'bot wd');
  const stateDir = join(root, `${channel}-state`);
  mkdirSync(botWd, { recursive: true });
  mkdirSync(stateDir, { recursive: true });
  return {
    root,
    botWd,
    stateDir,
    rcPath: join(root, '.zshrc'),
    channel,
    aliasName: '봇공부',
    sessionName: 'study-bot',
  };
}

test('skills make the launcher a REQUIRED bot-creation step, with explicit refusal (recorded in bot.yaml) as the only skip', () => {
  // 2026-08-12: «기본 추천(default-yes)» → «🔴 필수» 승격 (재경님 alias 생략
  // 회귀 수리). 앵커도 승격 후 문구로 — 구 문구 앵커는 승격 커밋이 남긴
  // 미스윕 회귀였다.
  const discord = readFileSync('skills/create-bot/SKILL.md', 'utf8');
  const slack = readFileSync('skills/slack-configure/SKILL.md', 'utf8');
  const entry = readFileSync('skills/create-slack-bot/SKILL.md', 'utf8');
  const legacy = readFileSync('commands/slack-configure.md', 'utf8');
  for (const text of [discord, slack]) {
    assert.match(text, /🔴 필수/);
    assert.match(text, /명시적 거부만 예외/);
    assert.match(text, /install-bot-launcher\.mjs/);
  }
  assert.match(slack, /\.slack-configure-target/);
  assert.doesNotMatch(slack, /\.slack-configure-state-dir/);
  assert.match(entry, /런처/);
  assert.match(legacy, /런처/);
  assert.doesNotMatch(slack, /alias \$BOT_NAME='cd \$BOT_DIR && claude/);
});

test('generated launcher uses exact tmux targets and contains no developer-machine path', () => {
  const text = launcherScript({
    channel: 'discord',
    aliasName: '봇공부',
    sessionName: 'study-bot',
    botWd: '/confirmed/work dir',
    stateDir: '/confirmed/state',
    wikiPath: '/confirmed/wiki path',
  });
  assert.match(text, /has-session -t "=\$SESSION_NAME"/);
  assert.match(text, /kill-session -t "=\$SESSION_NAME"/);
  assert.match(text, /attach-session -t "=\$SESSION_NAME"/);
  assert.match(text, /DISCORD_STATE_DIR/);
  assert.match(text, /export THISCODE_WIKI_PATH='\/confirmed\/wiki path'/);
  assert.match(text, /--channels plugin:discord@claude-plugins-official/);
  assert.doesNotMatch(text, /kill-server/);
  const forbiddenMachinePaths = new RegExp([
    ['', 'Users', 'tofu_mac'].join('/'),
    ['', 'home', 'tofu'].join('/'),
  ].join('|'));
  assert.doesNotMatch(text, forbiddenMachinePaths);
});

test('installer writes one idempotent managed rc block and backs up an existing rc', () => {
  const f = fixture();
  writeFileSync(f.rcPath, '# operator config\n');
  const first = installBotLauncher({ ...f, apply: true });
  const second = installBotLauncher({ ...f, apply: true });
  const rc = readFileSync(f.rcPath, 'utf8');
  assert.equal((rc.match(/>>> thiscode bot launcher:봇공부 >>>/g) || []).length, 1);
  assert.match(rc, /alias 봇공부=/);
  assert.match(rc, /alias 봇공부-stop=/);
  assert.equal(first.launcherPath, second.launcherPath);
  assert.ok(readdirSync(f.root).some(name => name.startsWith('.zshrc.thiscode-backup-')));
  assert.equal((readFileSync(first.launcherPath, 'utf8').match(/thiscode-bot-launcher v1/g) || []).length, 1);
  const sourced = spawnSync('/bin/bash', ['-c', 'source "$1"; alias 봇공부; alias 봇공부-stop', 'bash', f.rcPath], {
    encoding: 'utf8',
  });
  assert.equal(sourced.status, 0, sourced.stderr);
  assert.match(sourced.stdout, /\.thiscode-bot-launcher\.sh.*start/);
  assert.match(sourced.stdout, /\.thiscode-bot-launcher\.sh.*stop/);
  rmSync(f.root, { recursive: true, force: true });
});

test('tmux replay kills only the exact stale session and starts its replacement', () => {
  const f = fixture();
  const installed = installBotLauncher({ ...f, apply: true });
  const fakeBin = join(f.root, 'bin');
  const log = join(f.root, 'tmux.log');
  mkdirSync(fakeBin);
  const fakeTmux = join(fakeBin, 'tmux');
  writeFileSync(fakeTmux, `#!/bin/bash\nprintf '%s\\n' "$*" >> "$TMUX_LOG"\ncase "$1" in has-session) exit 0;; *) exit 0;; esac\n`);
  chmodSync(fakeTmux, 0o755);
  const run = spawnSync('/bin/bash', [installed.launcherPath, 'start'], {
    encoding: 'utf8',
    env: { ...process.env, PATH: `${fakeBin}:/usr/bin:/bin`, TMUX_LOG: log, THISCODE_LAUNCH_DETACH: '1' },
  });
  assert.equal(run.status, 0, run.stderr);
  const calls = readFileSync(log, 'utf8');
  assert.match(calls, /has-session -t =study-bot/);
  assert.match(calls, /kill-session -t =study-bot/);
  assert.match(calls, /new-session .* -s study-bot .* -c .*bot wd/);
  assert.doesNotMatch(calls, /kill-server|=study-bot2/);
  rmSync(f.root, { recursive: true, force: true });
});

test('without tmux, Discord and Slack launch in the confirmed WD with separated state env', () => {
  for (const channel of ['discord', 'slack']) {
    const f = fixture(channel);
    const installed = installBotLauncher({ ...f, apply: true });
    const fakeBin = join(f.root, 'bin');
    const log = join(f.root, 'agent.log');
    mkdirSync(fakeBin);
    const fakeClaude = join(fakeBin, 'claude');
    writeFileSync(fakeClaude, `#!/bin/bash\nprintf 'cwd=%s\\ndiscord=%s\\nslack=%s\\nwiki=%s\\nargs=%s\\n' "$PWD" "${'$'}{DISCORD_STATE_DIR:-}" "${'$'}{CLAUDE_CHANNEL_SLACK_DIR:-}" "${'$'}{THISCODE_WIKI_PATH:-}" "$*" > "$AGENT_LOG"\n`);
    chmodSync(fakeClaude, 0o755);
    const run = spawnSync('/bin/bash', [installed.launcherPath, channel === 'slack' ? 'safe' : 'start'], {
      encoding: 'utf8',
      env: {
        ...process.env,
        DISCORD_STATE_DIR: '/tmp/preexisting-discord-state',
        CLAUDE_CHANNEL_SLACK_DIR: '/tmp/preexisting-slack-state',
        THISCODE_WIKI_PATH: '/tmp/preexisting-wiki-path',
        PATH: fakeBin,
        AGENT_LOG: log,
      },
    });
    assert.equal(run.status, 0, run.stderr);
    const actual = readFileSync(log, 'utf8');
    assert.match(actual, new RegExp(`cwd=${f.botWd.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
    assert.match(actual, /wiki=\n/);
    if (channel === 'discord') {
      assert.match(actual, new RegExp(`discord=${f.stateDir.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
      assert.match(actual, /--channels plugin:discord@claude-plugins-official/);
      assert.match(actual, /slack=\n/);
    } else {
      assert.match(actual, new RegExp(`slack=${f.stateDir.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
      assert.match(actual, /--dangerously-load-development-channels server:slack-channel/);
      assert.doesNotMatch(actual, /--dangerously-skip-permissions/);
      assert.match(actual, /discord=\n/);
    }
    rmSync(f.root, { recursive: true, force: true });
  }
});
