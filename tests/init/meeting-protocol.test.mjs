import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const INIT_HOOK = fileURLToPath(new URL('../../hooks/bot-session-init.sh', import.meta.url));
const STOP_HOOK = fileURLToPath(new URL('../../hooks/meeting-stop-reread.sh', import.meta.url));

function normalize(text) {
  return text.replace(/\r\n/g, '\n');
}

test('meeting-protocol rule is routed from rules INDEX', () => {
  const rule = normalize(readFileSync('rules/meeting-protocol.md', 'utf8'));
  const index = normalize(readFileSync('rules/INDEX.md', 'utf8'));
  assert.match(rule, /SessionStart/i);
  assert.match(rule, /dispatch/i);
  assert.match(rule, /KST/i);
  assert.match(index, /meeting-protocol\.md/);
});

test('install-hooks command wires the meeting Stop hook', () => {
  const install = normalize(readFileSync('commands/install-hooks.md', 'utf8'));
  assert.match(install, /"Stop"/);
  assert.match(install, /meeting-stop-reread\.sh/);
});

test('SessionStart hook injects active meeting and rules index when present', () => {
  const home = mkdtempSync(join(tmpdir(), 'mp-home-'));
  const cwd = mkdtempSync(join(tmpdir(), 'mp-cwd-'));
  const meetingDir = join(cwd, 'meetings');
  const rulesDir = join(cwd, 'rules');
  const stateDir = join(home, '.claude', 'channels', 'discord-reviewer');
  mkdirSync(meetingDir, { recursive: true });
  mkdirSync(rulesDir, { recursive: true });
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(join(stateDir, 'soul.md'), '# reviewer soul\n');
  writeFileSync(join(meetingDir, 'ACTIVE.md'), '# active meeting\nThread: 123\n');
  writeFileSync(join(rulesDir, 'INDEX.md'), '# Rules INDEX\nmeeting-protocol.md\n');

  const stdout = execFileSync('bash', [INIT_HOOK], {
    cwd,
    encoding: 'utf8',
    env: { PATH: process.env.PATH, HOME: home, DISCORD_STATE_DIR: stateDir, MEETING_PROTOCOL_DIR: meetingDir, RULES_DIR: rulesDir },
  });

  assert.match(stdout, /active meeting/i);
  assert.match(stdout, /Rules INDEX/);
  rmSync(home, { recursive: true, force: true });
  rmSync(cwd, { recursive: true, force: true });
});

test('meeting Stop hook only continues for bot active-meeting non-recursive stop', () => {
  const cwd = mkdtempSync(join(tmpdir(), 'mp-stop-'));
  const meetingDir = join(cwd, 'meetings');
  mkdirSync(meetingDir, { recursive: true });
  writeFileSync(join(meetingDir, 'ACTIVE.md'), '# active meeting\n');

  const yes = spawnSync('bash', [STOP_HOOK], {
    cwd,
    encoding: 'utf8',
    input: JSON.stringify({ hook_event_name: 'Stop', stop_hook_active: false }),
    env: { ...process.env, BOT_WD: cwd, DISCORD_STATE_DIR: join(cwd, 'discord-reviewer'), MEETING_PROTOCOL_DIR: meetingDir },
  });
  assert.equal(yes.status, 0);
  const payload = JSON.parse(yes.stdout);
  assert.equal(payload.continue, true);
  assert.match(payload.reason, /active meeting/i);
  assert.match(payload.hookSpecificOutput.additionalContext, /ACTIVE\.md/);

  const recursive = spawnSync('bash', [STOP_HOOK], {
    cwd,
    encoding: 'utf8',
    input: JSON.stringify({ hook_event_name: 'Stop', stop_hook_active: true }),
    env: { ...process.env, BOT_WD: cwd, DISCORD_STATE_DIR: join(cwd, 'discord-reviewer'), MEETING_PROTOCOL_DIR: meetingDir },
  });
  assert.equal(recursive.status, 0);
  assert.equal(recursive.stdout.trim(), '');
  rmSync(cwd, { recursive: true, force: true });
});
