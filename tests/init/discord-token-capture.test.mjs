// discord-token-capture.sh — the bot token reaches .env without passing through the conversation.
//
// Two routes, both fixed code: clipboard (arm → copy → capture) and a prompt the user runs in
// their own terminal (paste). Each OS branch is exercised with stand-in clipboard commands put
// first on PATH; the stand-ins keep the "clipboard" in a file. WSL itself is not measured here.
//
// Isolation: HOME is a temp folder. Token-shaped values are built from repeated letters.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
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
  for (const name of ['cat', 'chmod', 'mkdir', 'mv', 'rm', 'grep', 'mktemp']) {
    const real = spawnSync('/bin/sh', ['-c', `command -v ${name}`], { encoding: 'utf8' }).stdout.trim();
    symlinkSync(real, join(bin, name));
  }
  const env = { HOME: home, PATH: bin };
  if (wayland || kind === 'wayland') env.WAYLAND_DISPLAY = 'wayland-0';
  const run = (...args) => spawnSync('/bin/bash', [SCRIPT, ...args], { encoding: 'utf8', env });
  const envFile = join(home, '.claude', 'channels', 'discord-mybot', '.env');
  return {
    home, clip, envFile, run,
    copy: value => writeFileSync(clip, value),
    clipboard: () => readFileSync(clip, 'utf8'),
    calls: () => (existsSync(called) ? readFileSync(called, 'utf8').trim().split('\n') : []),
  };
}

const mode = path => (statSync(path).mode & 0o777).toString(8);
const everything = result => result.stdout + result.stderr;

for (const kind of ['darwin', 'wsl', 'wayland', 'xclip']) {
  test(`${kind}: arm plants the marker, capture checks it, saves a 0600 .env, clears the clipboard, prints no value`, { skip: SKIP }, () => {
    const b = box(kind);
    assert.equal(b.run('arm').status, 0);
    assert.equal(b.clipboard(), MARKER);

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
    b.copy(value);
    const result = b.run('capture', 'mybot');
    assert.equal(result.status, 1, JSON.stringify(value.slice(0, 20)));
    assert.match(result.stderr, new RegExp(`사유 코드: ${code}`));
    if (value) assert.ok(!everything(result).includes(value), 'a refused value is not printed either');
  }
  assert.ok(!existsSync(b.envFile));
  assert.ok(!existsSync(join(b.home, 'ran')), 'nothing in the clipboard was run');
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
    for (const args of [['arm'], ['capture', 'mybot']]) {
      const result = b.run(...args);
      assert.equal(result.status, 4, `${kind} ${args[0]}`);
      assert.match(result.stderr, /여기서 멈춥니다/);
      assert.match(result.stderr, /paste/);
      assert.match(result.stderr, /대화 창에 붙여 넣지 마세요/);
    }
    assert.ok(!existsSync(b.envFile));
  }
  // Wayland session but no wl-clipboard and no xclip → the same stop
  assert.equal(box('xclip', { tools: false, wayland: true }).run('arm').status, 4);
});

test('other keys in .env are kept, the token line is replaced, a symlinked .env is refused', { skip: SKIP }, () => {
  const b = box('darwin');
  mkdirSync(join(b.envFile, '..'), { recursive: true });
  writeFileSync(b.envFile, 'OTHER=1\nDISCORD_BOT_TOKEN=old\n');
  chmodSync(b.envFile, 0o644);
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

test('paste: refuses when there is no terminal, so an agent shell cannot take this route', { skip: SKIP }, () => {
  const b = box('darwin');
  const result = spawnSync('/bin/bash', [SCRIPT, 'paste', 'mybot'], { encoding: 'utf8', env: { HOME: b.home, PATH: '/usr/bin:/bin' }, input: `${SHAPED}\n` });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /자기 터미널/);
  assert.ok(!existsSync(b.envFile), 'a value piped in is not accepted');
});

test('paste: in a real terminal the value is read hidden and saved 0600', { skip: SKIP || (spawnSync('python3', ['-c', 'import pty']).status !== 0 ? 'needs python3 pty to make a terminal' : false) }, () => {
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
  for (const call of ['discord-token-capture.sh arm', 'discord-token-capture.sh capture <bot-name>', 'discord-token-capture.sh paste <bot-name>']) {
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
    assert.match(text, /discord-token-capture\.sh capture <bot-name>/, `${path}: points at the fixed script`);
    assert.match(text, /discord-token-capture\.sh paste <bot-name>/, `${path}: and at the terminal route`);
    assert.match(text, /대화 창에 붙여 넣지 않는다/, path);
  }
});
