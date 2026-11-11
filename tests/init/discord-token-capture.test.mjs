// discord-token-capture.sh — the bot token reaches .env without passing through the conversation.
//
// Two routes, both fixed code: clipboard (arm → copy → capture) and a prompt the user runs in
// their own terminal (paste). Each OS branch is exercised with stand-in clipboard commands put
// first on PATH; the stand-ins keep the "clipboard" in a file. WSL itself is not measured here.
//
// Isolation: HOME is a temp folder. Token-shaped values are built from repeated letters.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, renameSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import test from 'node:test';

const WINDOWS = process.platform === 'win32';
const SKIP = WINDOWS ? 'the stand-in commands are shell scripts' : false;
const SCRIPT = resolve('scripts/discord-token-capture.sh');
const MARKER = 'THISCODE_NOT_COPIED_YET';
const SHAPED = `${'A'.repeat(24)}.${'b'.repeat(6)}.${'C'.repeat(38)}`;   // shape only, not a token

// A sandbox with a fake uname and fake clipboard commands for one OS branch.
function box(kind, { tools = true, wayland = false } = {}) {
  const home = mkdtempSync(join(tmpdir(), 'token-capture-'));
  const bin = join(home, 'bin');
  const clip = join(home, 'clipboard');
  mkdirSync(bin);
  writeFileSync(clip, 'something old');
  const put = (name, body) => { writeFileSync(join(bin, name), `#!/bin/sh\n${body}\n`); chmodSync(join(bin, name), 0o755); };
  const called = join(home, 'called');
  const log = name => `echo ${name} >> "${called}"`;
  const unameS = kind === 'darwin' ? 'Darwin' : 'Linux';
  const unameR = kind === 'wsl' ? '6.6.87.2-microsoft-standard-WSL2' : '6.8.0-generic';
  put('uname', `case "$1" in -s) echo ${unameS} ;; -r) echo ${unameR} ;; *) echo ${unameS} ;; esac`);
  if (tools) {
    if (kind === 'darwin') {
      put('pbcopy', `${log('pbcopy')}; cat > "${clip}"`);
      put('pbpaste', `${log('pbpaste')}; cat "${clip}"`);
    } else if (kind === 'wsl') {
      put('clip.exe', `${log('clip.exe')}; cat > "${clip}"`);
      // PowerShell prints the value followed by CR LF
      put('powershell.exe', `${log('powershell.exe')}; [ "$1" = "-NoProfile" ] || exit 9; cat "${clip}"; printf '\\r\\n'`);
    } else if (kind === 'wayland') {
      put('wl-copy', `${log('wl-copy')}; if [ "$1" = "--clear" ]; then : > "${clip}"; else cat > "${clip}"; fi`);
      put('wl-paste', `${log('wl-paste')}; cat "${clip}"`);
    } else {
      put('xclip', `${log('xclip')}; case "$*" in *-o*) cat "${clip}" ;; *) cat > "${clip}" ;; esac`);
    }
  }
  // PATH is this folder only — the machine's real clipboard commands must not be reachable.
  for (const name of ['cat', 'chmod', 'mkdir', 'mv', 'rm', 'grep', 'mktemp', 'ls', 'wc', 'tr', 'od', 'date', 'stat']) {
    const real = spawnSync('/bin/sh', ['-c', `command -v ${name}`], { encoding: 'utf8' }).stdout.trim();
    symlinkSync(real, join(bin, name));
  }
  const env = { HOME: home, PATH: bin };
  if (wayland || kind === 'wayland') env.WAYLAND_DISPLAY = 'wayland-0';
  const run = (...args) => spawnSync('/bin/bash', [SCRIPT, ...args], { encoding: 'utf8', env });
  const envFile = join(home, '.claude', 'channels', 'discord-mybot', '.env');
  const armFile = join(home, '.thiscode', 'token-arm', 'mybot.arm');
  return {
    home, clip, envFile, run, bin, put, armFile,
    arm: (name = 'mybot') => run('arm', name),
    copy: value => writeFileSync(clip, value),
    clipboard: () => readFileSync(clip, 'utf8'),
    calls: () => (existsSync(called) ? readFileSync(called, 'utf8').trim().split('\n') : []),
  };
}

const mode = path => (statSync(path).mode & 0o777).toString(8);
const ARMED = new RegExp(`^${MARKER}:[0-9a-f]{32}$`);
const everything = result => result.stdout + result.stderr;

for (const kind of ['darwin', 'wsl', 'wayland', 'xclip']) {
  test(`${kind}: arm plants a one-time marker, capture checks it, saves a 0600 .env, clears the clipboard, prints no value`, { skip: SKIP }, () => {
    const b = box(kind);
    const armed = b.arm();
    assert.equal(armed.status, 0, everything(armed));
    assert.match(b.clipboard(), ARMED, 'marker + a fresh one-time value');
    const nonce = b.clipboard().split(':')[1];
    assert.ok(!everything(armed).includes(nonce), 'the one-time value is not printed');
    assert.equal(mode(b.armFile), '600');
    assert.equal(mode(join(b.armFile, '..')), '700');

    const early = b.run('capture', 'mybot');
    assert.equal(early.status, 1, 'the copy button was not pressed yet');
    assert.match(early.stderr, /사유 코드: clipboard-empty/);
    assert.ok(!existsSync(b.envFile), 'nothing saved');

    b.copy(SHAPED);
    const saved = b.run('capture', 'mybot');
    assert.equal(saved.status, 0, everything(saved));
    assert.equal(readFileSync(b.envFile, 'utf8'), `DISCORD_BOT_TOKEN=${SHAPED}\n`);
    assert.equal(mode(b.envFile), '600');
    assert.ok(!everything(saved).includes(SHAPED), 'the value is never printed');
    assert.match(saved.stdout, /길이 70자/);
    assert.equal(b.clipboard(), '', 'the clipboard is emptied after the save');
    assert.ok(!existsSync(b.armFile), 'the arm record is used up');
    // a second capture on the same arm reads nothing, whatever sits in the clipboard
    b.copy(SHAPED.replace(/A/g, 'Z'));
    const again = b.run('capture', 'mybot');
    assert.equal(again.status, 1);
    assert.match(again.stderr, /사유 코드: not-armed/);
    assert.equal(readFileSync(b.envFile, 'utf8'), `DISCORD_BOT_TOKEN=${SHAPED}\n`, 'the saved token is untouched');

    const expected = { darwin: ['pbcopy', 'pbpaste'], wsl: ['clip.exe', 'powershell.exe'], wayland: ['wl-copy', 'wl-paste'], xclip: ['xclip'] }[kind];
    for (const tool of expected) assert.ok(b.calls().includes(tool), `${kind} uses ${tool}`);
  });
}

test('refused without saving: a wrong shape, two lines, an empty clipboard', { skip: SKIP }, () => {
  const b = box('darwin');
  for (const [value, code] of [
    ['short', 'format-mismatch'],
    [`${SHAPED} extra words`, 'format-mismatch'],
    [`${SHAPED}\n${SHAPED}`, 'format-mismatch'],
    ['', 'clipboard-empty'],
    [`$(touch ${join(b.home, 'ran')})${'x'.repeat(60)}`, 'format-mismatch'],
  ]) {
    assert.equal(b.arm().status, 0);
    b.copy(value);
    const result = b.run('capture', 'mybot');
    assert.equal(result.status, 1, JSON.stringify(value.slice(0, 20)));
    assert.ok(!existsSync(b.armFile), 'a value was read, so this arm is used up');
    assert.match(result.stderr, new RegExp(`사유 코드: ${code}`));
    if (value) assert.ok(!everything(result).includes(value), 'a refused value is not printed either');
  }
  assert.ok(!existsSync(b.envFile));
  assert.ok(!existsSync(join(b.home, 'ran')), 'nothing in the clipboard was run');
  // a refused value does not stay in the clipboard (it may hold the token among other text)
  assert.equal(b.arm().status, 0);
  b.copy(`${SHAPED}\n${SHAPED}`);
  assert.equal(b.run('capture', 'mybot').status, 1);
  assert.equal(b.clipboard(), '', 'cleared after a refusal');
  // …but the marker and the arm record stay when nothing was copied, so capture can be tried again
  assert.equal(b.arm().status, 0);
  assert.equal(b.run('capture', 'mybot').status, 1);
  assert.match(b.clipboard(), ARMED);
  assert.ok(existsSync(b.armFile));
  b.copy(SHAPED);
  assert.equal(b.run('capture', 'mybot').status, 0, 'the same arm still works once the value is copied');
  // a name that fails the shape check is refused before anything else, and is not printed back
  const bare = box('xclip', { tools: false });
  const armed = bare.run('arm', '$(echo injected)');
  assert.equal(armed.status, 2);
  assert.ok(!armed.stderr.includes('injected'));
  assert.equal(bare.run('arm').status, 2, 'arm needs the bot name');
});

test('the reason codes this script names are codes install-gate.sh accepts', () => {
  const script = readFileSync(SCRIPT, 'utf8');
  const named = new Set([...script.matchAll(/사유 코드: ([a-z-]+)/g)].map(match => match[1]));
  const accepted = spawnSync('bash', ['scripts/install-gate.sh', '--reason-codes'], { encoding: 'utf8' }).stdout;
  assert.ok(named.size >= 3);
  for (const code of named) assert.match(accepted, new RegExp(`^${code}\\t`, 'm'), code);
});

test('no clipboard tool: stops with exit 4 and points at the terminal route, never at the chat', { skip: SKIP }, () => {
  for (const kind of ['darwin', 'wsl', 'xclip']) {
    const b = box(kind, { tools: false });
    for (const args of [['arm', 'mybot'], ['capture', 'mybot']]) {
      const result = b.run(...args);
      assert.equal(result.status, 4, `${kind} ${args[0]}`);
      assert.match(result.stderr, /여기서 멈춥니다/);
      assert.match(result.stderr, /paste/);
      assert.match(result.stderr, /대화 창에 붙여 넣지 마세요/);
    }
    assert.ok(!existsSync(b.envFile));
  }
  // Wayland session but no wl-clipboard and no xclip → the same stop
  assert.equal(box('xclip', { tools: false, wayland: true }).run('arm', 'mybot').status, 4);
});

test('other keys in .env are kept, the token line is replaced, a symlinked .env is refused', { skip: SKIP }, () => {
  const b = box('darwin');
  mkdirSync(join(b.envFile, '..'), { recursive: true });
  writeFileSync(b.envFile, 'OTHER=1\nDISCORD_BOT_TOKEN=old\n');
  chmodSync(b.envFile, 0o644);
  assert.equal(b.arm().status, 0);
  b.copy(SHAPED);
  assert.equal(b.run('capture', 'mybot').status, 0);
  assert.equal(readFileSync(b.envFile, 'utf8'), `OTHER=1\nDISCORD_BOT_TOKEN=${SHAPED}\n`);
  assert.equal(mode(b.envFile), '600');
  assert.deepEqual(readdirSync(join(b.envFile, '..')), ['.env'], 'no temp file left behind');

  const linked = box('darwin');
  mkdirSync(join(linked.envFile, '..'), { recursive: true });
  const elsewhere = join(linked.home, 'elsewhere');
  writeFileSync(elsewhere, '');
  symlinkSync(elsewhere, linked.envFile);
  assert.equal(linked.arm().status, 0);
  linked.copy(SHAPED);
  assert.equal(linked.run('capture', 'mybot').status, 3);
  assert.equal(readFileSync(elsewhere, 'utf8'), '');
  assert.equal(linked.clipboard(), SHAPED, 'not cleared when nothing was saved');
});

test('bot name: only letters, digits, - and _ — nothing that could leave the channels folder', { skip: SKIP }, () => {
  const b = box('darwin');
  b.copy(SHAPED);
  for (const name of ['', '../x', 'a/b', 'a b', 'a\nb', '$(id)', '.']) {
    assert.equal(b.run('capture', name).status, 2, JSON.stringify(name));
  }
  assert.ok(!existsSync(join(b.home, '.claude')));
});

test('paste: refuses when stdin is not a terminal — a guard against an accidental pipe, not a check that a person is typing', { skip: SKIP }, () => {
  const b = box('darwin');
  const result = spawnSync('/bin/bash', [SCRIPT, 'paste', 'mybot'], { encoding: 'utf8', env: { HOME: b.home, PATH: '/usr/bin:/bin' }, input: `${SHAPED}\n` });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /자기 터미널/);
  assert.ok(!existsSync(b.envFile), 'a value piped in is not accepted');
});

test('paste: on a terminal (here a pseudo-terminal made by this test — any program of the same user can make one) the value is read hidden and saved 0600', { skip: SKIP || (spawnSync('python3', ['-c', 'import pty']).status !== 0 ? 'needs python3 pty to make a terminal' : false) }, () => {
  const b = box('darwin');
  const driver = `
import os, pty, sys, time
pid, fd = pty.fork()
if pid == 0:
    os.execve('/bin/bash', ['/bin/bash', sys.argv[1], 'paste', 'mybot'], {'HOME': sys.argv[2], 'PATH': '/usr/bin:/bin'})
out = b''
while b'Enter' not in out:
    out += os.read(fd, 1024)
os.write(fd, (sys.argv[3] + '\\n').encode())
try:
    while True:
        chunk = os.read(fd, 1024)
        if not chunk: break
        out += chunk
except OSError:
    pass
_, status = os.waitpid(pid, 0)
sys.stdout.write(out.decode('utf-8', 'replace'))
sys.exit(os.waitstatus_to_exitcode(status))
`;
  const result = spawnSync('python3', ['-c', driver, SCRIPT, b.home, SHAPED], { encoding: 'utf8' });
  assert.equal(result.status, 0, everything(result));
  assert.ok(!everything(result).includes(SHAPED), 'not echoed while typing, not printed after');
  assert.equal(readFileSync(b.envFile, 'utf8'), `DISCORD_BOT_TOKEN=${SHAPED}\n`);
  assert.equal(mode(b.envFile), '600');
});

test('create-bot text: the token is never asked for in the conversation, and both routes are the fixed script', () => {
  const skill = readFileSync('skills/create-bot/SKILL.md', 'utf8');
  const step4 = skill.slice(skill.indexOf('### Step 4. '), skill.indexOf('### Step 4.7.'));
  assert.ok(step4.length > 300);
  assert.doesNotMatch(step4.split('\n')[0], /AskUserQuestion|입력/, 'the heading no longer says the token is asked for');
  assert.match(step4, /토큰을 물어보는 질문\(AskUserQuestion 포함\)을 열지 않고/, 'the only mention of a question is the rule against it');
  assert.equal(step4.match(/AskUserQuestion/g).length, 1);
  assert.doesNotMatch(step4, /토큰 입력 요청/);
  assert.doesNotMatch(step4, /<입력 토큰>/, 'no token placeholder inside a command');
  assert.doesNotMatch(step4, /<<EOF/, 'no heredoc that would carry the value');
  for (const call of ['discord-token-capture.sh arm <bot-name>', 'discord-token-capture.sh capture <bot-name>', 'discord-token-capture.sh paste <bot-name>']) {
    assert.ok(step4.includes(call), call);
  }
  assert.match(step4, /복사했어요/);
  assert.match(step4, /대화 창에 붙여 넣지/);
  assert.doesNotMatch(skill, /제가 여는 입력 칸/);
  assert.doesNotMatch(skill, /결과\(토큰·초대 서버\)만 받는다/);
  const table = readFileSync('skills/create-bot/automation.yaml', 'utf8');
  assert.doesNotMatch(table, /제가 여는 입력 칸/);
  const row = table.slice(table.indexOf('gate: "discord_token_save"'), table.indexOf('- id: "4.7"'));
  assert.match(row, /복사했어요/);
  assert.match(row, /handoff_no_clipboard: "[^"]*paste/);
});

test('no skill or command shows a token placeholder inside a command or asks for the token in chat', () => {
  const nets = [/<입력 토큰>/, /DISCORD_BOT_TOKEN=<[^>]*>/, /토큰을 (알려|입력해) ?주/, /토큰 입력 요청/, /제가 여는 입력 칸/];
  // bait: each net catches the wording it is for
  const bait = ['DISCORD_BOT_TOKEN=<입력 토큰>', 'DISCORD_BOT_TOKEN=<토큰>', '토큰을 알려 주세요', 'agent 가 사용자에게 토큰 입력 요청', '제가 여는 입력 칸에 붙여 넣어 주세요'];
  assert.equal(bait.filter(line => nets.some(net => net.test(line))).length, bait.length, 'bait');
  const files = [];
  const walk = dir => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (/\.(md|yaml)$/.test(entry.name)) files.push(path);
    }
  };
  walk('skills');
  walk('commands');
  assert.ok(files.length > 20);
  // skills/thiscode_agy tells the user to edit the .env file in an editor (a comment line and a
  // template), not to put the token into a command or the chat — outside this net.
  for (const path of files.filter(path => !path.startsWith(join('skills', 'thiscode_agy')))) {
    readFileSync(path, 'utf8').split('\n').forEach((line, index) => {
      for (const net of nets) assert.doesNotMatch(line, net, `${path}:${index + 1}`);
    });
  }
  for (const path of ['commands/start.md', 'commands/add-bot.md']) {
    const text = readFileSync(path, 'utf8');
    assert.match(text, /discord-token-capture\.sh arm <bot-name>/, `${path}: arm names the bot`);
    assert.match(text, /discord-token-capture\.sh capture <bot-name>/, `${path}: points at the fixed script`);
    assert.match(text, /discord-token-capture\.sh paste <bot-name>/, `${path}: and at the terminal route`);
    assert.match(text, /대화 창에 붙여 넣지 않는다/, path);
  }
});

test('commands/add-bot.md follows the same two questions as the skill: the terms box and the three wider permissions', () => {
  const text = readFileSync('commands/add-bot.md', 'utf8');
  assert.doesNotMatch(text, /약관 동의 칸 체크 → «만들기»/, 'no unasked tick');
  assert.match(text, /먼저 예\/아니오를 묻고 ‘예’ 를 받은 뒤에만 누른다/);
  assert.match(text, /기본 권한 11종\(`permissions=395137117248`\)/);
  assert.match(text, /‘예’ 를 받은 때만 더한다/);
  assert.doesNotMatch(text, /→ 같은 권한/);
});

test('capture without a fresh arm for this bot reads nothing: no arm, another bot\'s arm, an expired arm, a forged record', { skip: SKIP }, () => {
  // an old token-shaped value is sitting in the clipboard and nobody armed
  const cold = box('darwin');
  cold.copy(SHAPED);
  const refused = cold.run('capture', 'mybot');
  assert.equal(refused.status, 1);
  assert.match(refused.stderr, /사유 코드: not-armed/);
  assert.ok(!existsSync(cold.envFile), 'the old value is not saved');
  assert.ok(!cold.calls().includes('pbpaste'), 'the clipboard was not even read');
  assert.equal(cold.clipboard(), SHAPED, 'and not touched');

  // armed for another bot
  const other = box('darwin');
  assert.equal(other.arm('otherbot').status, 0);
  other.copy(SHAPED);
  assert.equal(other.run('capture', 'mybot').status, 1);
  assert.ok(!existsSync(other.envFile));
  assert.ok(!other.calls().includes('pbpaste'));
  // …and a record whose bot line was edited to fit is thrown away
  assert.equal(other.arm('otherbot').status, 0);
  const otherFile = join(other.home, '.thiscode', 'token-arm', 'otherbot.arm');
  writeFileSync(other.armFile, readFileSync(otherFile, 'utf8'));
  chmodSync(other.armFile, 0o600);
  other.copy(SHAPED);
  const moved = other.run('capture', 'mybot');
  assert.equal(moved.status, 1);
  assert.match(moved.stderr, /다른 봇/);
  assert.ok(!existsSync(other.armFile));

  // armed too long ago
  const late = box('darwin');
  assert.equal(late.arm().status, 0);
  const minutes = Number(readFileSync(SCRIPT, 'utf8').match(/^ARM_TTL_MIN=(\d+)$/m)[1]);
  const old = Math.floor(Date.now() / 1000) - minutes * 60 - 5;
  writeFileSync(late.armFile, readFileSync(late.armFile, 'utf8').replace(/armed_at=\d+/, `armed_at=${old}`));
  late.copy(SHAPED);
  const expired = late.run('capture', 'mybot');
  assert.equal(expired.status, 1);
  assert.match(expired.stderr, /사유 코드: not-armed/);
  assert.ok(!existsSync(late.envFile));
  assert.ok(!existsSync(late.armFile), 'an expired record is removed');
  // a record from the future is as bad
  assert.equal(late.arm().status, 0);
  writeFileSync(late.armFile, readFileSync(late.armFile, 'utf8').replace(/armed_at=\d+/, `armed_at=${old + 999999}`));
  assert.equal(late.run('capture', 'mybot').status, 1);

  // the record is a symlink, or its content is not what arm writes
  const forged = box('darwin');
  assert.equal(forged.arm().status, 0);
  const real = join(forged.home, 'real.arm');
  writeFileSync(real, readFileSync(forged.armFile, 'utf8'));
  spawnSync('/bin/rm', [forged.armFile]);
  symlinkSync(real, forged.armFile);
  forged.copy(SHAPED);
  assert.equal(forged.run('capture', 'mybot').status, 1, 'a symlinked record');
  assert.ok(!existsSync(forged.envFile));
  spawnSync('/bin/rm', [forged.armFile]);
  writeFileSync(forged.armFile, 'nonce=$(id)\nbot=mybot\narmed_at=now\n');
  chmodSync(forged.armFile, 0o600);
  assert.equal(forged.run('capture', 'mybot').status, 1, 'a record with the wrong shape');
  assert.ok(!existsSync(forged.envFile));

  // control: the same sandbox works once it is armed properly
  assert.equal(forged.arm().status, 0);
  forged.copy(SHAPED);
  assert.equal(forged.run('capture', 'mybot').status, 0);
});

test('arm replaces an older record with a new one-time value each time', { skip: SKIP }, () => {
  const b = box('darwin');
  assert.equal(b.arm().status, 0);
  const first = b.clipboard();
  assert.equal(b.arm().status, 0);
  assert.notEqual(b.clipboard(), first);
  // the first marker is now just "a value that is not the marker": refused, and the arm is used up
  b.copy(first);
  const result = b.run('capture', 'mybot');
  assert.equal(result.status, 1);
  assert.match(result.stderr, /사유 코드: format-mismatch/);
});

test('saved but the clipboard could not be emptied: exit 5, said in one line, not reported as done', { skip: SKIP }, () => {
  const b = box('darwin');
  // a pbcopy that takes a value but fails on empty input
  b.put('pbcopy', `v=$(cat); [ -n "$v" ] || exit 1; printf '%s' "$v" > "${b.clip}"`);
  assert.equal(b.arm().status, 0);
  b.copy(SHAPED);
  const result = b.run('capture', 'mybot');
  assert.equal(result.status, 5);
  assert.equal(readFileSync(b.envFile, 'utf8'), `DISCORD_BOT_TOKEN=${SHAPED}\n`, 'the token is saved');
  assert.match(result.stderr, /클립보드를 비우지 못했습니다 — 지금 다른 글자를 한 번 복사해 덮어 주세요/);
  assert.ok(!everything(result).includes(SHAPED));
  const skill = readFileSync('skills/create-bot/SKILL.md', 'utf8');
  assert.match(skill, /`exit 5`[^\n]*다른 글자를 한 번 복사/, 'the skill says what to tell the user on exit 5');
});

test('macOS: an inherited ACL on the bot folder does not survive — .env, the folder and the arm record end with no ACL', { skip: process.platform !== 'darwin' ? 'file ACLs are handled on macOS only' : false }, () => {
  const acl = path => spawnSync('/bin/ls', ['-lde', path], { encoding: 'utf8' }).stdout.trim().split('\n').slice(1);
  const b = box('darwin');
  const botDir = join(b.envFile, '..');
  const armDir = join(b.armFile, '..');
  for (const dir of [botDir, armDir]) {
    mkdirSync(dir, { recursive: true });
    const set = spawnSync('/bin/chmod', ['+a', 'everyone allow read,file_inherit,directory_inherit', dir]);
    assert.equal(set.status, 0);
    assert.equal(acl(dir).length, 1, 'bait: the ACL is really there before the run');
  }
  // bait: a file made in that folder inherits the entry, and chmod 600 alone does not remove it
  const probe = join(botDir, 'probe');
  writeFileSync(probe, 'x');
  chmodSync(probe, 0o600);
  assert.match(acl(probe).join('\n'), /everyone inherited allow read/, 'bait: mode 600 and still readable through the ACL');
  spawnSync('/bin/rm', [probe]);

  assert.equal(b.arm().status, 0);
  assert.deepEqual(acl(b.armFile), []);
  assert.deepEqual(acl(armDir), []);
  b.copy(SHAPED);
  const saved = b.run('capture', 'mybot');
  assert.equal(saved.status, 0, everything(saved));
  assert.equal(mode(b.envFile), '600');
  assert.equal(mode(botDir), '700');
  assert.deepEqual(acl(b.envFile), [], 'no ACL line on the token file');
  assert.deepEqual(acl(botDir), [], 'and none left on the folder to be inherited next time');
});

test('create-bot text: arm names the bot everywhere, the wait is the script\'s number, and the identity check points at a section that exists', () => {
  const minutes = readFileSync(SCRIPT, 'utf8').match(/^ARM_TTL_MIN=(\d+)$/m)[1];
  const skill = readFileSync('skills/create-bot/SKILL.md', 'utf8');
  const step4 = skill.slice(skill.indexOf('### Step 4. '), skill.indexOf('### Step 4.7.'));
  assert.match(step4, new RegExp(`${minutes}분 안`), 'the same number as ARM_TTL_MIN');
  assert.match(step4, /not-armed/);
  assert.doesNotMatch(skill, /Step 6\.8/, 'there is no Step 6.8');
  assert.match(step4, /«검증» 절/);
  assert.match(skill, /^## 검증$/m, 'the section it points at exists');
  assert.match(step4, /에이전트를 막는 권한 경계가 아니다/, 'the terminal check is not sold as a person check');
  for (const path of ['skills/create-bot/SKILL.md', 'skills/create-bot/automation.yaml', 'commands/start.md', 'commands/add-bot.md', 'docs/RECENT-CHANGES.md']) {
    readFileSync(path, 'utf8').split('\n').forEach((line, index) => {
      for (const match of line.matchAll(/discord-token-capture\.sh arm(.{0,12})/g)) {
        assert.match(match[1], /^ <bot-name>/, `${path}:${index + 1}: arm is always called with the bot name`);
      }
    });
  }
});

// A record that arm never wrote, sitting where capture looks. It is valid in every line; what is
// wrong is the folder it lies in. capture must refuse before reading the clipboard, and must not
// repair the folder and then believe what was already in it.
function planted(setup) {
  const b = box('darwin');
  const top = join(b.home, '.thiscode');
  const armDir = join(top, 'token-arm');
  setup({ b, top, armDir });
  writeFileSync(b.armFile, `nonce=${'0123456789abcdef'.repeat(2)}\nbot=mybot\narmed_at=${Math.floor(Date.now() / 1000)}\n`);
  chmodSync(b.armFile, 0o600);
  b.copy(SHAPED);
  return { b, top, armDir };
}
function refusedUnread(b, why) {
  const result = b.run('capture', 'mybot');
  assert.equal(result.status, 1, `${why}: ${everything(result)}`);
  assert.match(result.stderr, /사유 코드: not-armed/, why);
  assert.ok(!b.calls().includes('pbpaste'), `${why}: the clipboard was not read`);
  assert.equal(b.clipboard(), SHAPED, `${why}: and not touched`);
  assert.ok(!existsSync(b.envFile), `${why}: nothing saved`);
  assert.ok(existsSync(b.armFile), `${why}: the record is left where it was`);
}
const dirs = ({ top, armDir }) => { mkdirSync(armDir, { recursive: true }); chmodSync(top, 0o700); chmodSync(armDir, 0o700); };

test('capture checks the folders a record lies in before reading it: an arm folder others can write to', { skip: SKIP }, () => {
  const { b, armDir } = planted(at => { dirs(at); chmodSync(at.armDir, 0o777); });
  refusedUnread(b, 'arm folder 0777');
  assert.equal(mode(armDir), '777', 'the read path repairs nothing');
});

test('capture checks the folders a record lies in before reading it: ~/.thiscode others can write to', { skip: SKIP }, () => {
  const { b, top } = planted(at => { dirs(at); chmodSync(at.top, 0o777); });
  refusedUnread(b, '~/.thiscode 0777');
  assert.equal(mode(top), '777', 'the read path repairs nothing');
});

test('capture checks the folders a record lies in before reading it: ~/.thiscode is a link to another folder', { skip: SKIP }, () => {
  const { b } = planted(({ b, top }) => {
    const elsewhere = join(b.home, 'elsewhere');
    mkdirSync(join(elsewhere, 'token-arm'), { recursive: true });
    chmodSync(elsewhere, 0o700); chmodSync(join(elsewhere, 'token-arm'), 0o700);
    symlinkSync(elsewhere, top);
  });
  refusedUnread(b, 'linked ~/.thiscode');
});

test('capture checks the record file without repairing it: a record with wider modes is not narrowed and then believed', { skip: SKIP }, () => {
  const { b } = planted(dirs);
  chmodSync(b.armFile, 0o644);
  refusedUnread(b, 'record 0644');
  assert.equal(mode(b.armFile), '644', 'the read path repairs nothing');
});

test('macOS: capture refuses a record in an arm folder whose ACL lets others add files', { skip: process.platform !== 'darwin' ? 'file ACLs are handled on macOS only' : false }, () => {
  const acl = path => spawnSync('/bin/ls', ['-lde', path], { encoding: 'utf8' }).stdout.trim().split('\n').slice(1);
  const { b, armDir } = planted(at => {
    dirs(at);
    assert.equal(spawnSync('/bin/chmod', ['+a', 'everyone allow add_file,delete_child,list,search,file_inherit', at.armDir]).status, 0);
  });
  assert.equal(acl(armDir).length, 1, 'bait: the ACL is there');
  spawnSync('/bin/chmod', ['-N', b.armFile]);   // the record itself is clean; only its folder is not
  refusedUnread(b, 'arm folder with a write ACL');
  assert.equal(acl(armDir).length, 1, 'the read path repairs nothing');
});

test('control: a record in private folders is read, and a first-time user or one whose ~/.thiscode was 0755 goes through arm → capture', { skip: SKIP }, () => {
  // the same planted record, folders 0700: this is the same user writing the file, outside what the check is for
  const { b } = planted(dirs);
  assert.equal(b.run('capture', 'mybot').status, 0, 'positive control for the four refusals above');

  const first = box('darwin');
  assert.equal(first.arm().status, 0);
  first.copy(SHAPED);
  assert.equal(first.run('capture', 'mybot').status, 0, 'no ~/.thiscode before');

  const older = box('darwin');
  mkdirSync(join(older.home, '.thiscode'));
  chmodSync(join(older.home, '.thiscode'), 0o755);
  writeFileSync(join(older.home, '.thiscode', 'install-state.yaml'), 'mode: auto\n');
  assert.equal(older.arm().status, 0);
  assert.equal(mode(join(older.home, '.thiscode')), '700', 'arm (the write path) is where folders are repaired');
  older.copy(SHAPED);
  assert.equal(older.run('capture', 'mybot').status, 0, '~/.thiscode was 0755');
  assert.ok(existsSync(join(older.home, '.thiscode', 'install-state.yaml')), 'other files there are left alone');
});

test('arm repairs a folder that was open to others, and then throws away every record that was already in it', { skip: SKIP }, () => {
  const { b, armDir } = planted(at => { dirs(at); chmodSync(at.armDir, 0o777); });
  assert.equal(b.arm('otherbot').status, 0, 'arming a different bot repairs the folder');
  assert.equal(mode(armDir), '700');
  assert.deepEqual(readdirSync(armDir), ['otherbot.arm'], 'the record planted for mybot did not survive the repair');
  b.copy(SHAPED);
  const result = b.run('capture', 'mybot');
  assert.equal(result.status, 1);
  assert.match(result.stderr, /사유 코드: not-armed/);
  assert.ok(!existsSync(b.envFile));

  // control: in folders that were private all along, arming one bot leaves another bot's record alone
  const calm = box('darwin');
  assert.equal(calm.arm('mybot').status, 0);
  assert.equal(calm.arm('otherbot').status, 0);
  assert.deepEqual(readdirSync(join(calm.armFile, '..')).sort(), ['mybot.arm', 'otherbot.arm']);
});

const ROOT = process.getuid && process.getuid() === 0 ? 'root can delete anything' : false;

test('arm empties a folder that was open to others completely — files of any name, dot files, folders, links (the link, not what it points at)', { skip: SKIP }, () => {
  const { b, armDir } = planted(at => { dirs(at); chmodSync(at.armDir, 0o777); });
  const outside = join(b.home, 'outside.txt');
  writeFileSync(outside, 'keep me');
  writeFileSync(join(armDir, 'notes.txt'), 'x');
  writeFileSync(join(armDir, '.hidden.arm'), 'x');
  mkdirSync(join(armDir, 'sub.arm'));
  writeFileSync(join(armDir, 'sub.arm', 'inner'), 'x');
  symlinkSync(outside, join(armDir, 'link.arm'));
  symlinkSync(b.home, join(armDir, 'homelink'));
  const armed = b.arm('otherbot');
  assert.equal(armed.status, 0, everything(armed));
  assert.deepEqual(readdirSync(armDir), ['otherbot.arm'], 'nothing that was there before is left');
  assert.equal(mode(armDir), '700');
  assert.equal(readFileSync(outside, 'utf8'), 'keep me', 'a link was removed, not followed');
  assert.ok(existsSync(join(b.home, 'bin')), 'a link to a folder was removed, not followed');
});

test('arm stops when something in such a folder cannot be removed: the folder is left closed, the next arm starts with the clean-up again, capture refuses meanwhile', { skip: SKIP || ROOT }, () => {
  const { b, armDir } = planted(at => { dirs(at); chmodSync(at.armDir, 0o777); });
  const stuck = join(armDir, 'aaa.arm');
  mkdirSync(stuck);
  writeFileSync(join(stuck, 'inner'), 'x');
  chmodSync(stuck, 0o555);   // its content cannot be unlinked, so the folder cannot be removed
  try {
    const first = b.arm('otherbot');
    assert.equal(first.status, 3, everything(first));
    assert.match(first.stderr, /사유 코드: check-failed/);
    assert.match(first.stderr, /token-arm\.removed/, 'says how to get going again');
    assert.ok(!everything(first).includes('aaa'), 'names found in the folder are not echoed');
    assert.equal(mode(armDir), '0', 'left in a mode the read path refuses');
    assert.ok(!b.calls().includes('pbcopy'), 'nothing was put in the clipboard');

    const second = b.arm('otherbot');
    assert.equal(second.status, 3, 'the next arm does not take the folder for a private one');
    assert.equal(mode(armDir), '0');

    b.copy(SHAPED);
    for (const name of ['mybot', 'otherbot']) {
      const result = b.run('capture', name);
      assert.equal(result.status, 1, name);
      assert.match(result.stderr, /사유 코드: not-armed/, name);
    }
    assert.ok(!b.calls().includes('pbpaste'), 'the clipboard was not read');
    assert.equal(b.clipboard(), SHAPED);
    assert.ok(!existsSync(b.envFile), 'the planted record did not get a token saved');

    // the user moves the folder away, as the message says — then everything works again
    renameSync(armDir, `${armDir}.removed`);
    assert.equal(b.arm().status, 0);
    assert.deepEqual(readdirSync(armDir), ['mybot.arm']);
    b.copy(SHAPED);
    assert.equal(b.run('capture', 'mybot').status, 0);
  } finally {
    for (const dir of [armDir, `${armDir}.removed`]) {
      if (existsSync(dir)) { chmodSync(dir, 0o700); if (existsSync(join(dir, 'aaa.arm'))) chmodSync(join(dir, 'aaa.arm'), 0o755); }
    }
  }
});

test('a clean-up that was cut short does not leave a trusted folder behind: while it runs the folder is not 0700', { skip: SKIP || ROOT }, () => {
  // Stand-in rm that does nothing: the clean-up "runs" but removes nothing, as if it had been interrupted.
  const { b, armDir } = planted(at => { dirs(at); chmodSync(at.armDir, 0o777); });
  spawnSync('/bin/rm', [join(b.bin, 'rm')]);
  b.put('rm', 'exit 0');
  assert.equal(b.arm('otherbot').status, 3);
  assert.notEqual(mode(armDir), '700');
  b.copy(SHAPED);
  const result = b.run('capture', 'mybot');
  assert.equal(result.status, 1, 'the planted record is not believed');
  assert.match(result.stderr, /사유 코드: not-armed/);
  assert.ok(!existsSync(b.envFile));
  chmodSync(armDir, 0o700);   // only to look inside
  assert.ok(existsSync(b.armFile), 'bait: the planted record really was still there');
});

test('arm killed in the middle of the clean-up: the folder is not 0700 at that moment, so the planted record is not believed afterwards', { skip: SKIP || ROOT }, () => {
  const { b, armDir } = planted(at => { dirs(at); chmodSync(at.armDir, 0o777); });
  spawnSync('/bin/rm', [join(b.bin, 'rm')]);
  b.put('rm', 'kill -9 $PPID');   // the script dies at its first removal
  const killed = b.arm('otherbot');
  assert.notEqual(killed.status, 0);
  assert.notEqual(mode(armDir), '700', 'the clean-up runs before the folder becomes 0700');
  assert.ok(existsSync(b.armFile), 'bait: the planted record is still there');
  b.copy(SHAPED);
  const result = b.run('capture', 'mybot');
  assert.equal(result.status, 1);
  assert.match(result.stderr, /사유 코드: not-armed/);
  assert.ok(!existsSync(b.envFile));
});
