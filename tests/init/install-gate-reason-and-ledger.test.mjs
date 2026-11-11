// install-gate.sh — what may go into an attempt reason, and how the install log file is kept.
//
// 1. A failure reason is a code from a closed list (configs/install.yaml · attempt_reason_codes).
//    Free text — screen text, error text, a value — is refused (exit 2) and never written.
//    The docs must not show a free-text reason inside a command either: a reason composed into the
//    command source is run by the shell before this script sees it, so the script cannot stop that.
// 2. The install log file is 0600 in a 0700 folder whatever the umask, an existing 0644 file is
//    lowered before a write, and a symlink / non-regular file is never written to.
//
// Isolation: HOME, state and log all live in a temp folder. The user's ~/.thiscode is never touched.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { chmodSync, existsSync, linkSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const WINDOWS = process.platform === 'win32';
const NO_MODE = WINDOWS ? 'permission bits are not meaningful on Windows' : false;

function box() {
  const dir = mkdtempSync(join(tmpdir(), 'gate-reason-'));
  const logDir = join(dir, '.thiscode');
  const log = join(logDir, 'install-log.jsonl');
  const env = { ...process.env, HOME: dir, THISCODE_INSTALL_STATE: join(dir, 'state.yaml'), THISCODE_INSTALL_LOG: log };
  // umask 022 on purpose: the script, not the caller's umask, has to make the file private.
  const run = (...args) => spawnSync('bash', ['-c', 'umask 022; exec bash scripts/install-gate.sh "$@"', 'gate', ...args], { encoding: 'utf8', env });
  return { dir, logDir, log, run };
}

const mode = path => (statSync(path).mode & 0o777).toString(8);
const logText = b => (existsSync(b.log) ? readFileSync(b.log, 'utf8') : '');

function codes() {
  const yaml = readFileSync('configs/install.yaml', 'utf8');
  const list = yaml.slice(yaml.indexOf('attempt_reason_codes:'), yaml.indexOf('manual_allowed_without_attempt:'));
  return [...list.matchAll(/^\s*-\s*code:\s*(\S+)\s*\n\s*says:\s*"([^"]+)"/gm)].map(match => ({ code: match[1], says: match[2] }));
}

test('reason codes: a closed list in install.yaml, lower-case words with hyphens, each with a fixed sentence', () => {
  const list = codes();
  assert.ok(list.length >= 8, 'the list is there');
  assert.equal(new Set(list.map(item => item.code)).size, list.length, 'no code twice');
  for (const { code, says } of list) {
    assert.match(code, /^[a-z0-9]+(-[a-z0-9]+)*$/, code);
    assert.match(says, /문제$/, `${code}: the sentence fits «<사유>로 안 됐습니다»`);
  }
  assert.ok(list.some(item => item.code === 'other'), 'there is a catch-all');
});

test('--attempted: every listed code is accepted and the code is what gets written', () => {
  const b = box();
  for (const { code } of codes()) {
    assert.equal(b.run('--attempted', 'discord_intents', 'fail', code).status, 0, code);
  }
  const rows = logText(b).trim().split('\n').map(line => JSON.parse(line));
  assert.deepEqual(rows.map(row => row.detail), codes().map(item => item.code));
});

test('--attempted: anything that is not a listed code is refused, not written, and not echoed back', () => {
  const b = box();
  const marker = join(b.dir, 'marker');
  const refused = [
    `$(touch ${marker})`,
    `\`touch ${marker}\``,
    'copy failed',
    '버튼을 못 찾음',
    'element-not-found; touch x',
    'Element-Not-Found',
    'element_not_found',
    'element-not-found\nother',
    '"quoted"',
    "it's",
    'not-on-the-list',
  ];
  for (const value of refused) {
    const result = b.run('--attempted', 'discord_intents', 'fail', value);
    assert.equal(result.status, 2, JSON.stringify(value));
    assert.ok(!(result.stdout + result.stderr).includes(value), `the refused value is not printed back: ${JSON.stringify(value)}`);
    assert.match(result.stderr, /attempt_reason_codes/, 'the message says where the list is');
  }
  assert.equal(b.run('--attempted', 'discord_intents', 'fail').status, 2, 'a failure still needs a reason');
  assert.equal(b.run('--attempted', 'discord_intents', 'ok', 'some text').status, 2, 'a success takes no free text either');
  assert.ok(!existsSync(marker), 'nothing in a refused value was run');
  assert.equal(logText(b), '', 'nothing was written');
  assert.equal(b.run('--attempted', 'discord_intents', 'ok').status, 0, 'control: a plain success is recorded');
});

test('--handoff still counts three failed attempts when the reasons are codes', () => {
  const b = box();
  for (const round of [1, 2, 3]) {
    assert.equal(b.run('--handoff', 'discord_intents').status, 1, `before attempt ${round}`);
    assert.equal(b.run('--attempted', 'discord_intents', 'fail', 'click-no-effect').status, 0);
  }
  assert.equal(b.run('--handoff', 'discord_intents').status, 0);
});

test('install log: 0600 in a 0700 folder even under umask 022', { skip: NO_MODE }, () => {
  const b = box();
  assert.equal(b.run('--attempted', 'discord_intents', 'fail', 'click-no-effect').status, 0);
  assert.equal(mode(b.log), '600');
  assert.equal(mode(b.logDir), '700');
  assert.equal(b.run('discord_intents').status, 1, 'the plain verdict path writes through the same door');
  assert.equal(mode(b.log), '600');
});

test('install log: a file and folder that already exist as 0644 / 0755 are lowered before the write', { skip: NO_MODE }, () => {
  const b = box();
  mkdirSync(b.logDir, { mode: 0o755 });
  chmodSync(b.logDir, 0o755);
  writeFileSync(b.log, '');
  chmodSync(b.log, 0o644);
  assert.equal(b.run('--attempted', 'discord_intents', 'fail', 'click-no-effect').status, 0);
  assert.equal(mode(b.log), '600');
  assert.equal(mode(b.logDir), '700');
});

test('install log: a symlink or a non-regular file is never written to, and nothing is handed over on its word', { skip: WINDOWS ? 'symlinks need privileges on Windows' : false }, () => {
  const link = box();
  mkdirSync(link.logDir);
  const elsewhere = join(link.dir, 'elsewhere');
  writeFileSync(elsewhere, '');
  symlinkSync(elsewhere, link.log);
  const refused = link.run('--attempted', 'discord_intents', 'fail', 'click-no-effect');
  assert.equal(refused.status, 3, 'recording fails closed');
  assert.match(refused.stderr, /설치 기록 파일/);
  assert.equal(readFileSync(elsewhere, 'utf8'), '', 'the link target is untouched');
  // three "failures" already sitting behind the link must not open the hand-over
  writeFileSync(elsewhere, '{"kind":"attempt","gate":"discord_intents","result":"fail","detail":"x"}\n'.repeat(3));
  assert.equal(link.run('--handoff', 'discord_intents').status, 1, 'a log that cannot be trusted allows nothing');

  const folder = box();
  mkdirSync(folder.log, { recursive: true });
  assert.equal(folder.run('--attempted', 'discord_intents', 'fail', 'click-no-effect').status, 3, 'a directory in the place of the file');
  assert.deepEqual(readdirSync(folder.log), []);
});

test('docs: no command example passes free text as a reason, and the tables name the code list', () => {
  const files = [];
  const walk = dir => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (/\.(md|yaml)$/.test(entry.name)) files.push(path);
    }
  };
  for (const dir of ['skills', 'commands', 'docs']) walk(dir);
  const allowed = new Set(codes().map(item => item.code));
  let seen = 0;
  for (const path of files) {
    readFileSync(path, 'utf8').split('\n').forEach((line, index) => {
      for (const match of line.matchAll(/--attempted\s+(\S+)\s+(ok|fail|<ok\|fail>)(?:[ \t]+(\S+))?/g)) {
        seen += 1;
        const [, , outcome, next = ''] = match;
        const where = `${path}:${index + 1}`;
        assert.doesNotMatch(next, /^["'`$]/, `${where}: a reason is never a quoted string or an expansion — ${line.trim()}`);
        if (outcome === 'fail' && next && !next.startsWith('#') && !/^[)>|&;\\]/.test(next)) {
          assert.ok(next === '<사유' || allowed.has(next), `${where}: after fail comes a listed code or the placeholder <사유 코드> — ${line.trim()}`);
        }
      }
    });
  }
  assert.ok(seen >= 10, `the scan saw the command examples (${seen})`);
  for (const skill of readdirSync('skills').filter(name => existsSync(join('skills', name, 'automation.yaml')))) {
    const table = readFileSync(join('skills', skill, 'automation.yaml'), 'utf8');
    assert.match(table, /record: "시도마다 install-gate\.sh --attempted <gate> <ok\|fail> <사유 코드>/, `${skill}: record`);
    assert.match(table, /record_never: "[^"]*attempt_reason_codes/, `${skill}: record_never points at the list`);
  }
});

test('reason codes: the table inside the script and the list in install.yaml are the same, one sentence per code', () => {
  const b = box();
  const shown = b.run('--reason-codes');
  assert.equal(shown.status, 0);
  const table = shown.stdout.trim().split('\n').map(line => line.split('\t')).map(([code, says]) => ({ code, says }));
  assert.deepEqual(table, codes());
  assert.equal(logText(b), '', 'listing the codes writes nothing');
  const recorded = b.run('--attempted', 'discord_intents', 'fail', 'click-no-effect');
  assert.match(recorded.stdout, /click-no-effect — 눌러도 화면이 바뀌지 않는 문제/, 'the fixed sentence comes back with the record');
});

test('install log: a folder that is a symlink, or a file with a second hard link, is refused', { skip: WINDOWS ? 'symlinks need privileges on Windows' : false }, () => {
  const linkedDir = box();
  const real = join(linkedDir.dir, 'real');
  mkdirSync(real);
  symlinkSync(real, linkedDir.logDir);
  assert.equal(linkedDir.run('--attempted', 'discord_intents', 'fail', 'click-no-effect').status, 3, 'the folder is a symlink');
  assert.deepEqual(readdirSync(real), []);

  const twoNames = box();
  mkdirSync(twoNames.logDir);
  writeFileSync(twoNames.log, '');
  linkSync(twoNames.log, join(twoNames.dir, 'second-name'));
  assert.equal(twoNames.run('--attempted', 'discord_intents', 'fail', 'click-no-effect').status, 3, 'a second hard link');
  assert.equal(readFileSync(twoNames.log, 'utf8'), '');
});

test('install log: a folder someone pointed the log at is not re-moded, and a folder others can write is refused', { skip: NO_MODE }, () => {
  const mine = mkdtempSync(join(tmpdir(), 'gate-own-'));
  chmodSync(mine, 0o755);
  const env = { ...process.env, HOME: mine, THISCODE_INSTALL_STATE: join(mine, 'state.yaml'), THISCODE_INSTALL_LOG: join(mine, 'log.jsonl') };
  const run = (...args) => spawnSync('bash', ['scripts/install-gate.sh', ...args], { encoding: 'utf8', env });
  assert.equal(run('--attempted', 'discord_intents', 'fail', 'click-no-effect').status, 0);
  assert.equal(mode(mine), '755', 'a folder that is not ours keeps its mode');
  assert.equal(mode(join(mine, 'log.jsonl')), '600');
  chmodSync(mine, 0o777);
  assert.equal(run('--attempted', 'discord_intents', 'fail', 'click-no-effect').status, 3, 'others could swap the file there');
});

test('install log: reading is as strict as writing — audit and hand-over refuse what a write would refuse', { skip: WINDOWS ? 'symlinks need privileges on Windows' : false }, () => {
  const three = '{"ts":"t","kind":"attempt","gate":"discord_intents","result":"fail","detail":"other"}\n'.repeat(3);
  // a log behind a symlink: --audit does not read it
  const link = box();
  mkdirSync(link.logDir);
  const elsewhere = join(link.dir, 'elsewhere');
  writeFileSync(elsewhere, three);
  symlinkSync(elsewhere, link.log);
  const audit = link.run('--audit');
  assert.equal(audit.status, 2);
  assert.match(audit.stderr, /설치 기록 파일을 믿을 수 없어 읽지 않는다/);
  assert.doesNotMatch(audit.stdout, /위반 0 건/);

  // a log in a folder others can write: three failures there open nothing
  const open = mkdtempSync(join(tmpdir(), 'gate-open-'));
  chmodSync(open, 0o775);
  const openLog = join(open, 'log.jsonl');
  writeFileSync(openLog, three);
  chmodSync(openLog, 0o600);
  const env = { ...process.env, HOME: open, THISCODE_INSTALL_STATE: join(open, 'state.yaml'), THISCODE_INSTALL_LOG: openLog };
  const run = (...args) => spawnSync('bash', ['scripts/install-gate.sh', ...args], { encoding: 'utf8', env });
  assert.equal(run('--handoff', 'discord_intents').status, 1, 'not handed over on the word of that log');
  assert.equal(run('--audit').status, 2);
  // control: the same three lines in a private folder do open the hand-over
  const ok = box();
  mkdirSync(ok.logDir, { mode: 0o700 });
  writeFileSync(ok.log, three);
  assert.equal(ok.run('--handoff', 'discord_intents').status, 0, 'control');
  assert.equal(ok.run('--audit').status, 0, 'control: audit reads a log it can trust');
});

test('install log: a file that is not an install log is neither re-moded nor appended to', { skip: NO_MODE }, () => {
  const b = box();
  const script = join(b.dir, 'my-script.sh');
  writeFileSync(script, '#!/bin/sh\necho hi\n');
  chmodSync(script, 0o755);
  const env = { ...process.env, HOME: b.dir, THISCODE_INSTALL_STATE: join(b.dir, 'state.yaml'), THISCODE_INSTALL_LOG: script };
  const result = spawnSync('bash', ['scripts/install-gate.sh', '--attempted', 'discord_intents', 'fail', 'other'], { encoding: 'utf8', env });
  assert.equal(result.status, 3);
  assert.equal(readFileSync(script, 'utf8'), '#!/bin/sh\necho hi\n');
  assert.equal(mode(script), '755');
});
