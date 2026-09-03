// 플러그인 훅 자동 등록(hooks/hooks.json) + 봇 세션 래퍼(hooks/lib/bot-only.sh)
//
// 왜 이 파일이 있나: 훅은 지금까지 «설치 후 한 번 더» 등록해야 붙었다(settings.json 병합).
//   그걸 플러그인이 직접 싣게 바꾸면 편해지는 대신, 봇이 아닌 «모든» 세션에도 붙는다.
//   그 부작용을 막는 것이 래퍼 한 장이라, 래퍼가 조용히 망가지면 일반 세션에 답장 게이트가
//   붙는다 — 사람이 눈치채기 어려운 종류의 고장이다. 그래서 기계가 매번 잰다.
//
// 격리: HOME 은 항상 임시 디렉터리다(--home). 사용자의 실제 ~/.claude 는 읽지도 쓰지도 않는다.
//
// 이식성: 스크립트를 «실행»하는 시험은 bash 가 있을 때만, .py 시험은 python3 가 있을 때만
//   돈다. 없으면 PASS 로 위장하지 않고 SKIP 을 명시한다.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import {
  mkdtempSync, rmSync, readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, cpSync, symlinkSync,
  chmodSync, statSync,
} from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const HOOKS_JSON = join(REPO, 'hooks', 'hooks.json');
const BOT_ONLY = join(REPO, 'hooks', 'lib', 'bot-only.sh');
const INSTALL_HOOKS = join(REPO, 'scripts', 'install-hooks.sh');

const read = (p) => readFileSync(p, 'utf8');
const REQUIRED = [
  'bot-session-init.sh', 'discord-slash-cmd.sh', 'regression-self-check.sh', 'rule-router.sh',
  'dispatch-room-gate.py', 'meeting-stop-reread.sh', 'reply-gate.sh',
];

function works(bin, args, want) {
  try {
    const r = spawnSync(bin, args, { encoding: 'utf8' });
    return r.status === 0 && (r.stdout || '').includes(want);
  } catch {
    return false;
  }
}
const BASH = works('bash', ['-c', 'echo ok'], 'ok');
const PY = works('python3', ['-c', 'print("ok")'], 'ok');
const skipNoBash = BASH ? false : 'bash 가 없어 실행 시험을 건너뛴다 (문서·JSON 잠금 시험은 그대로 돈다)';
const skipNoPy = PY ? false : 'python3 가 없어 .py 훅 실행 시험을 건너뛴다';

function sh(args, opts = {}) {
  const r = spawnSync('bash', args, {
    encoding: 'utf8',
    env: { ...process.env, ...(opts.env || {}) },
    input: opts.input,
  });
  return { code: r.status, out: r.stdout ?? '', err: r.stderr ?? '' };
}

function withTmp(prefix, fn) {
  const dir = mkdtempSync(join(tmpdir(), prefix));
  try {
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}
const withHome = (fn) => withTmp('thiscode-pj-home-', (dir) => {
  mkdirSync(join(dir, '.claude'), { recursive: true });
  return fn(dir);
});
// hooks/ 를 통째로 복제한 «가짜 플러그인 루트» — hooks.json 을 손대는 시험용
const withPluginCopy = (fn) => withTmp('thiscode-pj-plugin-', (dir) => {
  cpSync(join(REPO, 'hooks'), join(dir, 'hooks'), { recursive: true });
  return fn(dir);
});

const settingsPath = (home) => join(home, '.claude', 'settings.json');
const settingsOf = (home) => JSON.parse(read(settingsPath(home)));
const commandsOf = (home) => {
  const j = settingsOf(home);
  const out = [];
  for (const ev of Object.keys(j.hooks || {}))
    for (const g of j.hooks[ev] || []) for (const h of g.hooks || []) if (h.command) out.push(h.command);
  return out;
};

// ───────────────────────────────────── P1 hooks.json 계약 (OS 무관)
test('P1 — hooks.json 이 JSON 으로 읽히고 4 이벤트에 훅 7개가 있다', () => {
  assert.ok(existsSync(HOOKS_JSON), 'hooks/hooks.json 이 없다 — 플러그인이 훅을 싣지 못한다');
  const j = JSON.parse(read(HOOKS_JSON));
  assert.deepEqual(Object.keys(j.hooks).sort(),
    ['PreToolUse', 'SessionStart', 'Stop', 'UserPromptSubmit'], '4 이벤트가 아니다');
  const perEvent = {};
  for (const ev of Object.keys(j.hooks)) perEvent[ev] = j.hooks[ev].flatMap((g) => g.hooks || []).length;
  assert.deepEqual(perEvent, { SessionStart: 1, UserPromptSubmit: 3, PreToolUse: 1, Stop: 2 },
    '이벤트별 훅 수가 install-hooks.sh 의 PATCH 블록과 다르다');
});

test('P1 — 훅 7개가 전부 등록돼 있고 «전부» 래퍼를 거친다', () => {
  const j = JSON.parse(read(HOOKS_JSON));
  const cmds = Object.keys(j.hooks).flatMap((ev) => j.hooks[ev].flatMap((g) => (g.hooks || []).map((h) => h.command)));
  assert.equal(cmds.length, 7, `명령이 7개가 아니다 (${cmds.length})`);
  for (const want of REQUIRED) {
    assert.equal(cmds.filter((c) => c.includes(`/hooks/${want}`)).length, 1, `${want} 가 정확히 1번 있지 않다`);
  }
  assert.equal(cmds.filter((c) => c.includes('/hooks/lib/bot-only.sh')).length, 7,
    '래퍼를 안 거치는 훅이 있다 — 그 훅은 일반 세션에서도 돈다');
  // 미끼: 등록한 적 없는 훅은 잡히면 안 된다(자가 고장 검출)
  assert.equal(cmds.filter((c) => c.includes('zzq-never-installed-hook')).length, 0, '미끼가 잡혔다 — 자가 고장났다');
});

test('P1 — ${CLAUDE_PLUGIN_ROOT} 를 풀면 파일이 실재한다', () => {
  const j = JSON.parse(read(HOOKS_JSON));
  const cmds = Object.keys(j.hooks).flatMap((ev) => j.hooks[ev].flatMap((g) => (g.hooks || []).map((h) => h.command)));
  const refs = new Set();
  for (const c of cmds) for (const m of c.matchAll(/\$\{CLAUDE_PLUGIN_ROOT\}(\/[A-Za-z0-9._/-]+)/g)) refs.add(m[1]);
  assert.ok(refs.size >= 8, `참조 경로를 ${refs.size}개만 뽑았다 — 정규식이 낡았다 (래퍼 1 + 훅 7)`);
  for (const rel of refs) assert.ok(existsSync(join(REPO, rel)), `hooks.json 이 없는 파일을 가리킨다: ${rel}`);
  assert.equal(existsSync(join(REPO, '/hooks/zzq-never-installed-hook.sh')), false, '미끼 파일이 실재한다 — 자가 고장났다');
});

test('P1 — matcher·timeout 이 install-hooks.sh 의 PATCH 블록과 «원문» 일치', () => {
  const script = read(INSTALL_HOOKS).replace(/\r\n/g, '\n');
  // 병합 모드 PATCH 가 이벤트·matcher·timeout 의 정본이다. 두 표현이 갈리면 여기서 잡힌다.
  const fromScript = {};
  for (const m of script.matchAll(/hooks\/([A-Za-z0-9._-]+)'", "timeout": (\d+)/g)) fromScript[m[1]] = Number(m[2]);
  assert.equal(Object.keys(fromScript).length, 7, 'PATCH 에서 훅·timeout 을 7개 못 뽑았다 — 정규식이 낡았다');

  const j = JSON.parse(read(HOOKS_JSON));
  const fromJson = {};
  for (const ev of Object.keys(j.hooks))
    for (const g of j.hooks[ev]) for (const h of g.hooks || []) {
      const name = (h.command.match(/\/hooks\/([A-Za-z0-9._-]+)"?$/) || [])[1];
      fromJson[name] = h.timeout;
    }
  assert.deepEqual(fromJson, fromScript, 'hooks.json 의 timeout 이 PATCH 블록과 다르다');

  const matcher = (script.match(/"matcher": "(mcp__[^"]+)"/) || [])[1];
  assert.ok(matcher, 'PATCH 에서 PreToolUse matcher 를 못 뽑았다');
  assert.equal(j.hooks.PreToolUse[0].matcher, matcher, 'PreToolUse matcher 가 PATCH 원문과 다르다');
  for (const ev of ['SessionStart', 'UserPromptSubmit', 'Stop'])
    assert.equal(j.hooks[ev][0].matcher, '', `${ev} matcher 가 빈 문자열(전체 매치)이 아니다`);
});

// ───────────────────────────────────── P2·P3 래퍼 (bash 필요)
function stubs(dir) {
  const mark = join(dir, 'ran.txt');
  const shStub = join(dir, 'stub.sh');
  writeFileSync(shStub, `#!/bin/bash\ncat > "${mark}"\nexit 2\n`);
  return { mark, shStub };
}

test('P2 — 래퍼 음성: DISCORD_STATE_DIR 없으면 대상이 «돌지 않고» 출력 0바이트·exit 0', { skip: skipNoBash }, () => {
  withTmp('thiscode-pj-stub-', (dir) => {
    const { mark, shStub } = stubs(dir);
    const r = sh(['-c', `env -u DISCORD_STATE_DIR bash "${BOT_ONLY}" "${shStub}"`], { input: '{"hook":"x"}' });
    assert.equal(r.code, 0, '일반 세션에서 0 이 아닌 코드로 끝났다');
    assert.equal(r.out, '', `stdout 이 비어 있지 않다: ${JSON.stringify(r.out)}`);
    assert.equal(existsSync(mark), false, '봇 세션이 아닌데 훅이 실행됐다 — 부작용 차단이 뚫렸다');
  });
});

test('P3 — 래퍼 양성: 봇 세션이면 실행 + stdin 전달 + 종료코드 전파', { skip: skipNoBash }, () => {
  withTmp('thiscode-pj-stub-', (dir) => {
    const { mark, shStub } = stubs(dir);
    const r = sh([BOT_ONLY, shStub], { env: { DISCORD_STATE_DIR: join(dir, 'discord-testbot') }, input: '{"hook":"payload"}' });
    assert.equal(r.code, 2, `종료코드가 전파되지 않았다 (stub 은 2 로 끝난다, 받은 값 ${r.code})`);
    assert.ok(existsSync(mark), '봇 세션인데 훅이 실행되지 않았다');
    assert.equal(read(mark), '{"hook":"payload"}', 'stdin 이 대상에게 그대로 가지 않았다');
  });
});

test('P3 — 래퍼 양성: .py 훅은 python3 로 실행된다', { skip: skipNoBash || skipNoPy }, () => {
  withTmp('thiscode-pj-stub-', (dir) => {
    const mark = join(dir, 'py-ran.txt');
    const pyStub = join(dir, 'stub.py');
    writeFileSync(pyStub, `import sys\nopen(r"${mark}", "w").write("py:" + sys.stdin.read())\nsys.exit(3)\n`);
    const r = sh([BOT_ONLY, pyStub], { env: { DISCORD_STATE_DIR: join(dir, 'discord-testbot') }, input: 'PAYLOAD' });
    assert.equal(r.code, 3, `.py 훅의 종료코드가 전파되지 않았다 (${r.code}) — bash 로 실행됐을 수 있다: ${r.err}`);
    assert.equal(read(mark), 'py:PAYLOAD', '.py 훅이 python3 로 stdin 을 받지 못했다');
  });
});

test('P3 — 래퍼: 대상 파일이 없으면 fail-open (stderr 1줄 · exit 0)', { skip: skipNoBash }, () => {
  const r = sh(['-c', `DISCORD_STATE_DIR=/tmp/zz-not-a-real-bot bash "${BOT_ONLY}" /nonexistent-hook.sh`], { input: '{}' });
  assert.equal(r.code, 0, '훅 파일이 없다고 세션을 막았다 — fail-open 이 아니다');
  assert.equal(r.out, '', 'stdout 으로 뭔가 새어 나갔다');
  assert.equal(r.err.trim().split('\n').length, 1, `stderr 가 1줄이 아니다: ${JSON.stringify(r.err)}`);
  assert.match(r.err, /실재하지 않는다/, '무엇이 없는지 알려주지 않는다');
});

// ───────────────────────────────────── P4 install-hooks 플러그인 모드 (bash 필요)
test('P4 — 플러그인 모드 기본 실행: 병합하지 않는다 (settings.json 을 만들지도 않는다)', { skip: skipNoBash }, () => {
  withHome((home) => {
    const r = sh([INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO]);
    assert.equal(r.code, 0, `실패했다: ${r.err}`);
    assert.match(r.out, /플러그인이 훅을 직접 싣는다/, '무슨 모드인지 알려주지 않는다');
    assert.match(r.out, /--verify/, '검사 방법을 알려주지 않는다');
    assert.equal(existsSync(settingsPath(home)), false, '병합하지 않기로 해 놓고 settings.json 을 만들었다');
  });
});

test('P4 — 플러그인 모드 --verify: exit 0 + enabledPlugins 없으면 «경고 1줄»(실패 아님)', { skip: skipNoBash }, () => {
  withHome((home) => {
    const r = sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]);
    assert.equal(r.code, 0, `검사가 실패했다: ${r.out}${r.err}`);
    assert.match(r.out, /검사 통과/, '통과 문구가 없다');
    const warn = r.out.split('\n').filter((l) => l.includes('미확인 — enabledPlugins'));
    assert.equal(warn.length, 1, `enabledPlugins 경고가 1줄이 아니다: ${r.out}`);
    assert.equal(/검사 실패/.test(r.out), false, '경고를 실패로 셌다 — 개발 체크아웃이 거짓 실패한다');
  });
});

test('P4 — enabledPlugins 에 thiscode 가 켜져 있으면 «등록 확인» 을 표시한다', { skip: skipNoBash }, () => {
  withHome((home) => {
    writeFileSync(settingsPath(home), JSON.stringify({ enabledPlugins: { 'thiscode@thiscode-marketplace': true } }, null, 2));
    const r = sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]);
    assert.equal(r.code, 0, `검사가 실패했다: ${r.out}`);
    assert.match(r.out, /등록 확인 — enabledPlugins/, 'enabledPlugins 를 읽지 않는다');
  });
});

test('P4 — 옛 병합 잔존을 지우고 백업을 남기며 «남의» 훅은 보존한다', { skip: skipNoBash }, () => {
  withHome((home) => {
    const stale = (n) => `bash '${REPO}/hooks/${n}'`;
    writeFileSync(settingsPath(home), JSON.stringify({
      model: 'opus',
      hooks: {
        SessionStart: [{ matcher: '', hooks: [{ type: 'command', command: stale('bot-session-init.sh'), timeout: 10 }] }],
        Stop: [{ matcher: '', hooks: [
          { type: 'command', command: stale('reply-gate.sh'), timeout: 5 },
          { type: 'command', command: "bash '/Users/somebody/my-own-hook.sh'", timeout: 7 },
        ] }],
      },
    }, null, 2));

    // 잔존이 있는 동안에는 --verify 가 «이중 발화» 로 실패해야 한다 (D4 ⑥)
    const before = sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]);
    assert.equal(before.code, 1, '옛 병합 항목이 남았는데 검사가 통과했다 — 이중 발화를 못 잡는다');
    assert.match(before.out, /옛 병합 항목 2 건 잔존/, '몇 건이 남았는지 알려주지 않는다');

    const r = sh([INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO]);
    assert.equal(r.code, 0, `실패했다: ${r.err}`);
    assert.match(r.out, /옛 병합 항목 2 건 제거/, '무엇을 지웠는지 알려주지 않는다');

    const cmds = commandsOf(home);
    assert.equal(cmds.filter((c) => c.includes(`${REPO}/hooks/`)).length, 0, '옛 병합 항목이 남아 있다');
    assert.equal(cmds.filter((c) => c.includes('my-own-hook.sh')).length, 1, '사용자의 기존 훅이 사라졌다');
    assert.equal(settingsOf(home).model, 'opus', '훅과 무관한 설정이 사라졌다');
    assert.equal(Object.keys(settingsOf(home).hooks).includes('SessionStart'), false,
      '훅이 0개가 된 이벤트가 껍데기로 남았다 — 「등록돼 있다」로 오독된다');

    const baks = readdirSync(join(home, '.claude')).filter((f) => f.includes('.bak-'));
    assert.equal(baks.length, 1, `백업이 1개가 아니다 (${baks.length})`);
    assert.match(read(join(home, '.claude', baks[0])), /reply-gate\.sh/, '백업에 지운 내용이 없다 — 되돌릴 수 없다');

    // 지운 뒤에는 검사가 통과한다
    assert.equal(sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]).code, 0, '지웠는데도 검사가 실패한다');
  });
});

test('P4 — 지울 것이 없으면 settings.json 을 손대지 않는다 (백업도 안 만든다)', { skip: skipNoBash }, () => {
  withHome((home) => {
    const body = JSON.stringify({ hooks: { Stop: [{ matcher: '', hooks: [{ type: 'command', command: "bash '/Users/somebody/my-own-hook.sh'" }] }] } }, null, 2);
    writeFileSync(settingsPath(home), body);
    assert.equal(sh([INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO]).code, 0);
    assert.equal(read(settingsPath(home)), body, '지울 것이 없는데 파일을 다시 썼다');
    assert.equal(readdirSync(join(home, '.claude')).filter((f) => f.includes('.bak-')).length, 0, '지운 것도 없이 백업을 만들었다');
  });
});

test('P4 — --dry-run 은 지울 목록만 보여주고 파일을 바꾸지 않는다', { skip: skipNoBash }, () => {
  withHome((home) => {
    const body = JSON.stringify({
      hooks: { Stop: [{ matcher: '', hooks: [{ type: 'command', command: `bash '${REPO}/hooks/reply-gate.sh'`, timeout: 5 }] }] },
    }, null, 2);
    writeFileSync(settingsPath(home), body);
    const r = sh([INSTALL_HOOKS, '--dry-run', '--home', home, '--plugin-dir', REPO]);
    assert.equal(r.code, 0);
    assert.match(r.out, /\[미리보기\]/, '미리보기 표시가 없다');
    assert.match(r.out, /reply-gate\.sh/, '지울 항목을 안 보여준다');
    assert.equal(read(settingsPath(home)), body, 'dry-run 이 파일을 바꿨다');
    assert.equal(readdirSync(join(home, '.claude')).filter((f) => f.includes('.bak-')).length, 0, 'dry-run 이 백업을 만들었다');
  });
});

// ───────────────────────────────────── P5 미끼 — 검사가 실제로 보는가
test('P4 — 잔존 자 = 훅 파일명: 마켓 캐시의 옛 버전 디렉터리·다른 체크아웃 경로도 지우고, 이름만 닮은 남의 훅은 남긴다', { skip: skipNoBash }, () => {
  withHome((home) => {
    writeFileSync(settingsPath(home), JSON.stringify({
      hooks: {
        SessionStart: [{ matcher: '', hooks: [
          { type: 'command', command: "bash '/Users/somebody/.claude/plugins/cache/mk/thiscode/1.2.7/hooks/bot-session-init.sh'", timeout: 10 },
        ] }],
        PreToolUse: [{ matcher: 'x', hooks: [
          { type: 'command', command: "python3 '/opt/other-checkout/hooks/dispatch-room-gate.py'", timeout: 5 },
        ] }],
        UserPromptSubmit: [{ matcher: '', hooks: [
          { type: 'command', command: "bash 'C:\\Users\\x\\.claude\\plugins\\cache\\mk\\thiscode\\1.2.7\\hooks\\rule-router.sh'", timeout: 3 },
        ] }],
        Stop: [{ matcher: '', hooks: [
          { type: 'command', command: "bash '/Users/somebody/hooks/reply-gate-custom.sh'", timeout: 7 },
        ] }],
      },
    }, null, 2));

    // 1.3.0 의 PLUGIN_DIR 과 경로가 다른 옛 항목 2건 — 경로 자로는 못 잡고 파일명 자로만 잡힌다
    const before = sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]);
    assert.equal(before.code, 1, '옛 버전 디렉터리·다른 체크아웃의 잔존을 못 잡았다 — 이중 발화가 통과한다');
    assert.match(before.out, /옛 병합 항목 3 건 잔존/, '잔존 건수가 3이 아니다 (닮은 이름을 세었거나 Windows 구분자 경로를 놓쳤다)');

    const r = sh([INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO]);
    assert.equal(r.code, 0, `실패했다: ${r.err}`);
    assert.match(r.out, /옛 병합 항목 3 건 제거/, '무엇을 지웠는지 알려주지 않는다');

    const cmds = commandsOf(home);
    assert.equal(cmds.filter((c) => /1\.2\.7|other-checkout/.test(c)).length, 0, '옛 경로의 잔존이 남아 있다 (Windows 구분자 포함)');
    assert.equal(cmds.filter((c) => c.includes('reply-gate-custom.sh')).length, 1, '이름만 닮은 남의 훅을 지웠다');
    assert.equal(sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]).code, 0, '지웠는데도 검사가 실패한다');
  });
});

test('P5 — 미끼: REQUIRED 하나를 뺀 hooks.json 은 --verify 가 1 로 잡는다', { skip: skipNoBash }, () => {
  withHome((home) => withPluginCopy((plug) => {
    const hj = join(plug, 'hooks', 'hooks.json');
    // ① 양성 대조 — 손대지 않은 사본은 통과한다(자가 고장 검출)
    assert.equal(sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', plug]).code, 0,
      '복제만 했는데 검사가 실패한다 — 미끼 이전에 자가 고장났다');

    // ② 돌연변이 — reply-gate 행만 뺀다
    const j = JSON.parse(read(hj));
    for (const ev of Object.keys(j.hooks))
      for (const g of j.hooks[ev]) g.hooks = (g.hooks || []).filter((h) => !h.command.includes('reply-gate.sh'));
    writeFileSync(hj, JSON.stringify(j, null, 2));
    const bad = sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', plug]);
    assert.equal(bad.code, 1, 'REQUIRED 훅을 뺐는데 검사가 통과했다 — 그 검사는 장식이다');
    assert.match(bad.out, /reply-gate\.sh/, '무엇이 빠졌는지 알려주지 않는다');
  }));
});

test('P5 — 미끼: hooks.json 이 가리키는 파일을 지우면 --verify 가 1 로 잡는다', { skip: skipNoBash }, () => {
  withHome((home) => withPluginCopy((plug) => {
    rmSync(join(plug, 'hooks', 'lib', 'bot-only.sh'), { force: true });
    const r = sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', plug]);
    assert.equal(r.code, 1, '래퍼가 없는데 검사가 통과했다 — 훅이 모든 세션에서 도는 상태를 못 잡는다');
    assert.match(r.out, /bot-only\.sh/, '무엇이 없는지 알려주지 않는다');
  }));
});

test('P5 — 미끼: hooks.json 이 깨지면 --verify 가 1 로 잡는다', { skip: skipNoBash }, () => {
  withHome((home) => withPluginCopy((plug) => {
    writeFileSync(join(plug, 'hooks', 'hooks.json'), '{ this is not json');
    const r = sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', plug]);
    assert.equal(r.code, 1, '깨진 JSON 인데 검사가 통과했다');
    assert.match(r.out, /JSON 으로 읽을 수 없다/, '파싱 실패라고 말하지 않는다');
  }));
});

// ───────────────────────────────────── P6 엔진 parity (jq 없는 PATH)
// jq 를 못 쓰는 환경(Windows 등)에서 node 폴백이 «같은 규칙» 인지 실측한다.
// PATH 에서 jq 만 빼는 건 불가능하다 — 필요한 도구만 담은 최소 PATH 를 만든다.
function minimalBin(dir) {
  const need = ['bash', 'node', 'dirname', 'date', 'cp', 'mv', 'rm', 'sed', 'grep', 'sort', 'cat', 'mkdir', 'awk'];
  const bin = join(dir, 'bin');
  mkdirSync(bin, { recursive: true });
  for (const t of need) {
    let src = null;
    for (const d of ['/bin', '/usr/bin']) if (existsSync(join(d, t))) { src = join(d, t); break; }
    if (t === 'node') src = process.execPath;
    if (!src) return null;
    symlinkSync(src, join(bin, t));
  }
  const probe = spawnSync(join(bin, 'bash'), ['-c', 'command -v jq'], { encoding: 'utf8', env: { PATH: bin } });
  if (probe.status === 0) return null; // jq 가 여전히 보이면 이 시험은 성립하지 않는다
  return bin;
}

test('P6 — jq 없는 PATH(node 엔진)에서도 같은 결과: 잔존 제거 + 검사 통과', { skip: skipNoBash }, (t) => {
  withHome((home) => withTmp('thiscode-pj-bin-', (dir) => {
    const bin = minimalBin(dir);
    if (!bin) return t.skip('최소 PATH 를 만들 수 없거나 jq 가 여전히 보인다 — node 전용 시험 불가');
    writeFileSync(settingsPath(home), JSON.stringify({
      hooks: { Stop: [{ matcher: '', hooks: [
        { type: 'command', command: `bash '${REPO}/hooks/reply-gate.sh'`, timeout: 5 },
        { type: 'command', command: "bash '/Users/somebody/my-own-hook.sh'", timeout: 7 },
      ] }] },
    }, null, 2));
    const env = { PATH: bin };
    const run = spawnSync(join(bin, 'bash'), [INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO], { encoding: 'utf8', env });
    assert.equal(run.status, 0, `node 엔진 실행이 실패했다: ${run.stderr}`);
    assert.match(run.stdout, /옛 병합 항목 1 건 제거/, 'node 엔진이 잔존을 못 지웠다 — jq 경로와 갈라졌다');
    const cmds = commandsOf(home);
    assert.equal(cmds.filter((c) => c.includes(`${REPO}/hooks/`)).length, 0, 'node 엔진이 잔존을 남겼다');
    assert.equal(cmds.filter((c) => c.includes('my-own-hook.sh')).length, 1, 'node 엔진이 남의 훅을 지웠다');
    const ver = spawnSync(join(bin, 'bash'), [INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO], { encoding: 'utf8', env });
    assert.equal(ver.status, 0, `node 엔진 검사가 실패했다: ${ver.stdout}`);
  }));
});

// ───────────────────────────────────── P7~P9 잔존 자의 «소유» 판정 (F1)
// 이름이 같다고 우리 것이 아니다. 이 시험들이 재는 것은 «남의 살아있는 훅을 안 지우는가» 다.
// 주의: 임시 디렉터리 이름에 thiscode 가 들어가면 소유 규칙(경로에 thiscode)이 먼저 걸려
//   시험이 성립하지 않는다 — 남의 것을 흉내 내는 경로는 중립 접두어로 만든다.
const withNeutralTmp = (fn) => withTmp('zz-user-side-', fn);

test('P7 — F1 음성: 이름만 같은 «살아있는 남의 훅» 은 지우지 않고 경고만 한다', { skip: skipNoBash }, () => {
  withHome((home) => withNeutralTmp((usr) => {
    const userHook = join(usr, 'user-hooks', 'hooks', 'rule-router.sh');
    mkdirSync(dirname(userHook), { recursive: true });
    writeFileSync(userHook, '#!/bin/bash\nexit 0\n');
    const body = JSON.stringify({
      hooks: { UserPromptSubmit: [{ matcher: '', hooks: [{ type: 'command', command: `bash '${userHook}'`, timeout: 3 }] }] },
    }, null, 2);
    writeFileSync(settingsPath(home), body);

    const dry = sh([INSTALL_HOOKS, '--dry-run', '--home', home, '--plugin-dir', REPO]);
    assert.equal(dry.code, 0, `dry-run 이 실패했다: ${dry.err}`);
    assert.match(dry.out, /지울 옛 병합 항목 없음/, '남의 살아있는 훅을 지울 목록에 올렸다');
    assert.match(dry.out, /주의 — 이름은 같지만 소유가 불명한 항목 1 건/, '손대지 않은 항목을 알려주지 않는다');

    const r = sh([INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO]);
    assert.equal(r.code, 0, `실패했다: ${r.err}`);
    assert.equal(read(settingsPath(home)), body, '지울 것이 없는데 파일을 다시 썼다');
    assert.equal(commandsOf(home).filter((c) => c.includes('rule-router.sh')).length, 1, '남의 살아있는 훅을 지웠다');

    const ver = sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]);
    assert.equal(ver.code, 0, `남의 훅 때문에 검사가 거짓 실패했다: ${ver.out}`);
  }));
});

test('P8 — F1 양성: 소유 표식(경로 thiscode·형제 plugin.json·죽은 항목·래퍼) 4종은 전부 지운다', { skip: skipNoBash }, () => {
  withHome((home) => withNeutralTmp((usr) => {
    // ⓒ 다른 체크아웃 — 경로에 thiscode 는 없지만 형제로 우리 plugin.json 이 실재한다
    const other = join(usr, 'other-checkout');
    mkdirSync(join(other, '.claude-plugin'), { recursive: true });
    mkdirSync(join(other, 'hooks'), { recursive: true });
    writeFileSync(join(other, '.claude-plugin', 'plugin.json'), JSON.stringify({ name: 'thiscode', version: '1.2.7' }, null, 2));
    writeFileSync(join(other, 'hooks', 'reply-gate.sh'), '#!/bin/bash\nexit 0\n');
    // ⓔ 래퍼를 앞세운 옛 병합 항목
    const wrapped = `bash "${join(usr, 'wrap', 'hooks', 'lib', 'bot-only.sh')}" "${join(usr, 'wrap', 'hooks', 'reply-gate.sh')}"`;

    writeFileSync(settingsPath(home), JSON.stringify({
      hooks: {
        SessionStart: [{ matcher: '', hooks: [
          { type: 'command', command: "bash '/Users/somebody/.claude/plugins/cache/mk/thiscode/1.2.7/hooks/reply-gate.sh'", timeout: 5 },
        ] }],
        UserPromptSubmit: [{ matcher: '', hooks: [
          { type: 'command', command: `bash '${join(other, 'hooks', 'reply-gate.sh')}'`, timeout: 5 },
        ] }],
        PreToolUse: [{ matcher: 'x', hooks: [
          { type: 'command', command: "python3 '/opt/nowhere-zzq/hooks/dispatch-room-gate.py'", timeout: 5 },
        ] }],
        Stop: [{ matcher: '', hooks: [
          { type: 'command', command: wrapped, timeout: 5 },
          { type: 'command', command: "bash '/Users/somebody/my-own-hook.sh'", timeout: 7 },
        ] }],
      },
    }, null, 2));

    const r = sh([INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO]);
    assert.equal(r.code, 0, `실패했다: ${r.err}`);
    assert.match(r.out, /옛 병합 항목 4 건 제거/, `소유 표식이 있는 4건을 다 못 지웠다: ${r.out}`);
    const cmds = commandsOf(home);
    assert.equal(cmds.length, 1, `남은 항목이 1개가 아니다: ${JSON.stringify(cmds)}`);
    assert.equal(cmds.filter((c) => c.includes('my-own-hook.sh')).length, 1, '대조군(우리 것이 아닌 훅)을 지웠다');
    assert.equal(sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]).code, 0, '지웠는데도 검사가 실패한다');
  }));
});

test('P9 — F1 변수 경로: 전개하지 않은 $HOME 경로를 «죽은 항목» 으로 오판하지 않는다', { skip: skipNoBash }, () => {
  withHome((home) => {
    const body = JSON.stringify({
      hooks: { Stop: [{ matcher: '', hooks: [{ type: 'command', command: 'bash "$HOME/x/hooks/reply-gate.sh"', timeout: 5 }] }] },
    }, null, 2);
    writeFileSync(settingsPath(home), body);
    const dry = sh([INSTALL_HOOKS, '--dry-run', '--home', home, '--plugin-dir', REPO]);
    assert.match(dry.out, /지울 옛 병합 항목 없음/, '변수 경로를 «파일 부재» 로 읽고 지우려 한다');
    assert.match(dry.out, /주의 — 이름은 같지만 소유가 불명한 항목 1 건/, '불명 항목이라고 알려주지 않는다');
    assert.equal(sh([INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO]).code, 0);
    assert.equal(read(settingsPath(home)), body, '보존해야 할 항목을 지웠다');
    assert.equal(sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]).code, 0, '거짓 실패한다');
  });
});

// ───────────────────────────────────── P10 «래퍼 경유» 를 주장만 하지 않는가 (F2)
test('P10 — F2: 래퍼를 우회한 hooks.json 을 --verify 가 1 로 잡는다', { skip: skipNoBash }, () => {
  withHome((home) => withPluginCopy((plug) => {
    const hj = join(plug, 'hooks', 'hooks.json');
    const j = JSON.parse(read(hj));
    for (const ev of Object.keys(j.hooks))
      for (const g of j.hooks[ev]) for (const h of g.hooks || [])
        h.command = h.command.replace('bash "${CLAUDE_PLUGIN_ROOT}/hooks/lib/bot-only.sh" ', 'bash ');
    const mutated = Object.keys(j.hooks).flatMap((ev) => j.hooks[ev].flatMap((g) => (g.hooks || []).map((h) => h.command)));
    assert.equal(mutated.filter((c) => c.includes('bot-only.sh')).length, 0, '미끼가 안 심겼다 — 명령에 래퍼가 남아 있다');
    assert.equal(mutated.length, 7, `명령이 7개가 아니다 (${mutated.length})`);
    writeFileSync(hj, JSON.stringify(j, null, 2));

    const r = sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', plug]);
    assert.equal(r.code, 1, '7훅 전부 래퍼를 우회하는데 검사가 통과했다 — 「래퍼 경유」는 주장일 뿐이다');
    assert.match(r.out, /래퍼를 거치지 않는 명령 7 건/, `우회 건수를 안 알려준다: ${r.out}`);
  }));
});

// ───────────────────────────────────── P11 파싱 실패 ≠ 잔존 0 (F4)
test('P11 — F4: settings.json 을 못 읽으면 «잔존 0» 이 아니라 실패다 (파일 무접촉)', { skip: skipNoBash }, () => {
  withHome((home) => {
    const broken = '{"hooks":';
    writeFileSync(settingsPath(home), broken);
    assert.equal(sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]).code, 1,
      '깨진 settings.json 을 「검사 통과」로 읽었다');
    assert.equal(sh([INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO]).code, 2,
      '못 읽는 파일에 손을 대고 성공이라 했다');
    assert.equal(read(settingsPath(home)), broken, '깨진 파일의 바이트가 바뀌었다');
    assert.equal(readdirSync(join(home, '.claude')).filter((f) => f.includes('.bak-')).length, 0, '읽지도 못한 파일을 백업했다');

    // 0 바이트는 «없음» 과 같이 본다 — 경고는 하되 실패로 세지 않는다
    writeFileSync(settingsPath(home), '');
    const empty = sh([INSTALL_HOOKS, '--verify', '--home', home, '--plugin-dir', REPO]);
    assert.equal(empty.code, 0, `빈 파일을 실패로 셌다: ${empty.out}`);
    assert.match(empty.out, /비어 있다/, '비어 있다고 알려주지 않는다');
  });
});

// ───────────────────────────────────── P12 제자리 쓰기 (F5)
test('P12 — F5: 잔존을 지워도 settings.json 의 권한이 넓어지지 않는다', { skip: skipNoBash }, (t) => {
  if (process.platform === 'win32') return t.skip('Windows 에는 POSIX 권한 비트가 없다');
  return withHome((home) => {
    writeFileSync(settingsPath(home), JSON.stringify({
      hooks: { Stop: [{ matcher: '', hooks: [
        { type: 'command', command: `bash '${REPO}/hooks/reply-gate.sh'`, timeout: 5 },
        { type: 'command', command: "bash '/Users/somebody/my-own-hook.sh'", timeout: 7 },
      ] }] },
    }, null, 2));
    chmodSync(settingsPath(home), 0o600);
    const r = sh([INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO]);
    assert.equal(r.code, 0, `실패했다: ${r.err}`);
    assert.match(r.out, /옛 병합 항목 1 건 제거/, '잔존을 안 지웠다 — 권한 시험이 성립하지 않는다');
    const mode = statSync(settingsPath(home)).mode & 0o777;
    assert.equal(mode.toString(8), '600', `권한이 600 에서 ${mode.toString(8)} 로 넓어졌다`);
  });
});

// ───────────────────────────────────── P13 값 없는 인자 (F9)
test('P13 — F9: 값 없는 --home/--plugin-dir 은 무한 루프가 아니라 rc 2 로 끝난다', { skip: skipNoBash }, () => {
  const r = spawnSync('bash', [INSTALL_HOOKS, '--home'], { encoding: 'utf8', timeout: 5000 });
  assert.equal(r.status, 2, `rc 가 2 가 아니다 (${r.status} · signal ${r.signal}) — 값 없는 인자에서 멈추지 않는다`);
  assert.equal(r.stdout ?? '', '', 'stdout 으로 뭔가 샜다');
  assert.equal((r.stderr ?? '').trim().split('\n').length, 1, `stderr 가 1줄이 아니다: ${JSON.stringify(r.stderr)}`);
  const r2 = spawnSync('bash', [INSTALL_HOOKS, '--plugin-dir'], { encoding: 'utf8', timeout: 5000 });
  assert.equal(r2.status, 2, `--plugin-dir 도 같아야 한다 (${r2.status} · signal ${r2.signal})`);
});

// ───────────────────────────────────── P14 계수 자 (F6)
test('P14 — F6: 개행이 든 명령 1건을 1건으로 센다 (줄 수가 아니라 항목 수)', { skip: skipNoBash }, () => {
  withHome((home) => {
    const cmd = "bash '/opt/nowhere-zzq/hooks/reply-gate.sh'\nbash '/opt/nowhere-zzq/hooks/rule-router.sh'";
    writeFileSync(settingsPath(home), JSON.stringify({
      hooks: { Stop: [{ matcher: '', hooks: [{ type: 'command', command: cmd, timeout: 5 }] }] },
    }, null, 2));
    const dry = sh([INSTALL_HOOKS, '--dry-run', '--home', home, '--plugin-dir', REPO]);
    assert.match(dry.out, /지울 옛 병합 항목 1 건/, `개행을 항목으로 셌다: ${dry.out}`);
    const r = sh([INSTALL_HOOKS, '--home', home, '--plugin-dir', REPO]);
    assert.match(r.out, /옛 병합 항목 1 건 제거/, `제거 계수도 1 이어야 한다: ${r.out}`);
    assert.equal(commandsOf(home).length, 0, '개행이 든 명령을 못 지웠다');
  });
});

// ───────────────────────────────────── P15 인터프리터 부재·확장자 (F10·F8)
test('P15 — F10: python3 가 없으면 rc127 이 아니라 건너뛴다 (stderr 1줄 · exit 0)', { skip: skipNoBash }, (t) => {
  return withTmp('thiscode-pj-nopy-', (dir) => {
    const bin = join(dir, 'bin');
    mkdirSync(bin, { recursive: true });
    for (const tool of ['bash', 'cat']) {
      let src = null;
      for (const d of ['/bin', '/usr/bin']) if (existsSync(join(d, tool))) { src = join(d, tool); break; }
      if (!src) return t.skip('최소 PATH 를 만들 수 없다');
      symlinkSync(src, join(bin, tool));
    }
    const probe = spawnSync(join(bin, 'bash'), ['-c', 'command -v python3'], { encoding: 'utf8', env: { PATH: bin } });
    if (probe.status === 0) return t.skip('최소 PATH 에서도 python3 가 보인다 — 이 시험은 성립하지 않는다');
    const pyStub = join(dir, 'stub.py');
    writeFileSync(pyStub, 'import sys\nsys.exit(3)\n');
    const r = spawnSync(join(bin, 'bash'), [BOT_ONLY, pyStub], {
      encoding: 'utf8', input: '{"hook":"x"}', env: { PATH: bin, DISCORD_STATE_DIR: join(dir, 'discord-testbot') },
    });
    assert.equal(r.status, 0, `python3 가 없다고 rc ${r.status} 로 끝났다 — fail-open 계약이 깨진다`);
    assert.equal(r.stdout ?? '', '', 'stdout 으로 뭔가 샜다');
    assert.equal((r.stderr ?? '').trim().split('\n').length, 1, `stderr 가 1줄이 아니다: ${JSON.stringify(r.stderr)}`);
    assert.match(r.stderr, /python3 이 없어/, '무엇이 없어서 건너뛰는지 알려주지 않는다');
    return undefined;
  });
});

test('P15 — F8: 대문자 .PY 확장자도 python3 로 실행한다', { skip: skipNoBash || skipNoPy }, () => {
  withTmp('thiscode-pj-stub-', (dir) => {
    const mark = join(dir, 'py-upper-ran.txt');
    const pyStub = join(dir, 'stub-upper.PY');
    writeFileSync(pyStub, `import sys\nopen(r"${mark}", "w").write("PY:" + sys.stdin.read())\nsys.exit(3)\n`);
    const r = sh([BOT_ONLY, pyStub], { env: { DISCORD_STATE_DIR: join(dir, 'discord-testbot') }, input: 'PAYLOAD' });
    assert.equal(r.code, 3, `.PY 훅이 python3 로 실행되지 않았다 (${r.code}) — bash 로 넘어갔다: ${r.err}`);
    assert.equal(read(mark), 'PY:PAYLOAD', '.PY 훅이 python3 로 stdin 을 받지 못했다');
  });
});
