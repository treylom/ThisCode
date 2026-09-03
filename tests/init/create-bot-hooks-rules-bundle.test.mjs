// create-bot 훅·규칙 동봉 — 「봇이 답을 만들고도 터미널에만 찍는」 사고의 재발 방지
//
// 왜 이 파일이 있나: 2026-09-03 외부 사용자가 create-bot 으로 만든 봇이 답장을 터미널에만
//   띄웠다. 원인은 훅이 «자동으로 붙지 않는다»는 것과, 생성물 안에 reply 규칙이 0줄이라는 것.
//   둘 다 문서 한 줄이라 조용히 되돌아간다 — 그래서 기계가 잡는다.
//
// 격리: HOME 을 임시 디렉터리로 돌린다(--home). 사용자의 실제 ~/.claude 는 건드리지 않는다.
//
// 이식성(H6): 스크립트를 «실행»하는 시험은 bash 가 있을 때만 돈다. 없으면 PASS 로 위장하지
//   않고 SKIP 을 명시한다 — windows-latest 가 이 저장소의 최빈 실패 축이라, 「돌지 않았는데
//   초록」이 제일 위험하다. 문서 잠금 시험은 OS 와 무관하게 항상 돈다.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const INSTALL_HOOKS = join(REPO, 'scripts', 'install-hooks.sh');
const GATE = join(REPO, 'scripts', 'install-gate.sh');
const CREATE_BOT = join(REPO, 'skills', 'create-bot', 'SKILL.md');
const IH_SKILL = join(REPO, 'skills', 'install-hooks', 'SKILL.md');

const read = (p) => readFileSync(p, 'utf8');

// bash 가 실제로 «도는지» 본다 (존재 확인만으로는 부족 — 있는데 못 도는 환경이 있다)
function bashWorks() {
  try {
    const r = spawnSync('bash', ['-c', 'echo ok'], { encoding: 'utf8' });
    return r.status === 0 && (r.stdout || '').trim() === 'ok';
  } catch {
    return false;
  }
}
const BASH = bashWorks();
const skipNoBash = BASH ? false : 'bash 가 없어 스크립트 실행 시험을 건너뛴다 (문서 잠금 시험은 그대로 돈다)';

function withHome(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'thiscode-hooks-'));
  try {
    mkdirSync(join(dir, '.claude'), { recursive: true });
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function sh(args, env = {}) {
  const r = spawnSync('bash', args, { encoding: 'utf8', env: { ...process.env, ...env } });
  return { code: r.status, out: r.stdout ?? '', err: r.stderr ?? '' };
}

const settingsOf = (home) => JSON.parse(read(join(home, '.claude', 'settings.json')));
const commandsOf = (home) => {
  const j = settingsOf(home);
  const out = [];
  for (const ev of Object.keys(j.hooks || {}))
    for (const g of j.hooks[ev] || []) for (const h of g.hooks || []) if (h.command) out.push(h.command);
  return out;
};

// ─────────────────────────────────────────────── H1 문서·파일 (OS 무관)
test('H1 — install-hooks.sh 가 존재하고 필요한 선택지를 갖는다', () => {
  assert.ok(existsSync(INSTALL_HOOKS), 'scripts/install-hooks.sh 가 없다');
  const src = read(INSTALL_HOOKS);
  for (const opt of ['--dry-run', '--home', '--plugin-dir', '--verify']) {
    assert.ok(src.includes(opt), `${opt} 선택지가 없다`);
  }
  assert.match(src, /bak-/, '백업 파일 이름 규칙이 없다');
  // jq 없을 때 node 로 «같은 규칙»을 쓴다는 계약 (Windows 축)
  assert.match(src, /command -v node/, 'jq 부재 시 node 폴백이 없다');
  assert.match(src, /exit 2/, 'jq·node 둘 다 없을 때의 종료코드가 없다');
});

test('H1 — 병합 로직이 두 곳에 복제돼 있지 않다 (SKILL 은 스크립트를 부른다)', () => {
  const ih = read(IH_SKILL);
  assert.ok(ih.includes('scripts/install-hooks.sh'), 'install-hooks SKILL 이 스크립트를 부르지 않는다');
  assert.equal(ih.includes('def uniqHooks'), false,
    '병합식이 SKILL.md 에 그대로 남아 있다 — 스크립트와 갈라진다');
});

// ─────────────────────────────────────────────── H2 reply-gate (OS 무관)
test('H2 — install-hooks SKILL 의 훅 목록에 reply-gate 행이 있다', () => {
  const ih = read(IH_SKILL);
  assert.match(ih, /reply-gate\.sh/, '훅 목록에 reply-gate.sh 가 없다');
  assert.match(ih, /터미널에만 찍힌 출력은 사용자에게 \*\*도달하지 않는다\*\*/,
    'reply-gate 가 왜 필요한지가 안 적혀 있다');
});

test('H2 — 스크립트가 Stop 에 reply-gate.sh 를 넣는다 (원본 문자열)', () => {
  assert.match(read(INSTALL_HOOKS), /hooks\/reply-gate\.sh/, '병합 대상에 reply-gate.sh 가 없다');
});

// ─────────────────────────────────────────────── H3 Step 6.7 ④⑤ · 규칙 씨앗 (OS 무관)
test('H3 — create-bot Step 6.7 에 ④ 훅 등록 · ⑤ 규칙 동봉이 있다', () => {
  const cb = read(CREATE_BOT);
  assert.match(cb, /④ 훅 등록/, '④ 훅 등록 절이 없다');
  assert.match(cb, /⑤ 규칙 동봉/, '⑤ 규칙 동봉 절이 없다');
  assert.ok(cb.includes('scripts/install-hooks.sh'), 'create-bot 이 같은 스크립트를 부르지 않는다');
  assert.ok(cb.includes('rules/INDEX.md') && cb.includes('rules/discord-comms.md'),
    '동봉할 규칙 2개가 지정돼 있지 않다');
  assert.match(cb, /매 응답 전 `rules\/INDEX\.md` 트리거 표를 self-check/,
    '생성 CLAUDE.md 에 넣을 1줄이 없다');
});

test('H3 — 시도 기록 «후» 게이트 재호출 금지가 문면에 있다', () => {
  // 재호출하면 새 판정이 쌓여 --audit 이 빨개진다(2026-09-03 실측). 문서가 이걸 알아야 한다.
  assert.match(read(CREATE_BOT), /뒤에 게이트를 다시 부르지 않는다/,
    '게이트 재호출 금지가 안 적혀 있다 — 그대로 두면 감사가 빨개진다');
});

test('H3 — Step 7 시동 안내 직전에 --verify 검사가 있다', () => {
  const cb = read(CREATE_BOT);
  assert.match(cb, /install-hooks\.sh --verify --home/, 'Step 7 앞의 실제 검사가 없다');
  const verifyAt = cb.indexOf('install-hooks.sh --verify --home "$HOME"');
  const guideAt = cb.indexOf('**`--channels` 플래그가 없으면');
  assert.ok(verifyAt >= 0 && guideAt >= 0, '검사 또는 안내 앵커를 못 찾았다');
  assert.ok(verifyAt < guideAt, '검사가 시동 안내보다 뒤에 있다 — 순서가 뒤집혔다');
});

test('H3 — rules-seed 가 v1.2.0 이고 Rule 0(답장 도구)이 맨 앞이다', () => {
  const seed = read(join(REPO, 'templates', 'rules-seed.md'));
  assert.match(seed, /rules-seed v1\.2\.0/, '버전이 v1.2.0 이 아니다');
  assert.match(seed, /## Rule 0 —/, 'Rule 0 이 없다');
  assert.match(seed, /터미널에 찍은\s*\n?출력은 사용자 화면에 \*\*도달하지 않는다\*\*/,
    'Rule 0 의 핵심 문장이 없다');
  assert.ok(seed.indexOf('## Rule 0') < seed.indexOf('## Rule 1'), 'Rule 0 이 Rule 1 보다 뒤에 있다');
});

// ─────────────────────────────────────────────── H4 게이트 (OS 무관 — install-gate 는 bash 필요)
test('H4 — 두 관문은 install.yaml 명단에 없다 (미등재 = 시도 강제)', () => {
  const yaml = read(join(REPO, 'configs', 'install.yaml'));
  const start = yaml.indexOf('manual_allowed_without_attempt:');
  assert.ok(start >= 0, '명단 블록을 못 찾았다');
  const names = [...yaml.slice(start).matchAll(/^\s*-\s*name:\s*([A-Za-z0-9_]+)/gm)].map((m) => m[1]);
  assert.ok(names.length >= 6, `이름을 ${names.length}개만 뽑았다 — 정규식이 낡았다`);
  assert.ok(names.includes('discord_portal_login'), '양성 대조 — 알려진 등재명이 안 잡힌다');
  for (const g of ['hooks_installed', 'rules_seeded']) {
    assert.ok(!names.includes(g), `${g} 가 명단에 있다 — 게이트가 공허해진다(항상 exit 0)`);
  }
});

test('H4 — 시도 전 exit 1 → 기록하면 감사 위반 0', { skip: skipNoBash }, () => {
  withHome((home) => {
    const env = {
      THISCODE_INSTALL_STATE: join(home, 'install-state.yaml'),
      THISCODE_INSTALL_LOG: join(home, 'install-log.jsonl'),
    };
    writeFileSync(env.THISCODE_INSTALL_STATE, 'install:\n  mode: auto\n');
    for (const g of ['hooks_installed', 'rules_seeded']) {
      assert.equal(sh([GATE, g], env).code, 1, `${g} 는 미등재라 「먼저 시도할 것」(1)이어야 한다`);
      assert.equal(sh([GATE, '--attempted', g, 'ok'], env).code, 0);
    }
    const audit = sh([GATE, '--audit'], env);
    assert.equal(audit.code, 0, '기록했는데도 감사가 위반을 낸다');
    assert.match(audit.out, /위반 0 건/);
  });
});

// ─────────────────────────────────────────────── H1/H2 실행 실증 (bash 필요)
test('H1 — 임시 HOME 머지: 4 이벤트 · reply-gate 1 · 기존 타 훅 잔존 · 미끼 0', { skip: skipNoBash }, () => {
  withHome((home) => {
    // 사용자가 이미 갖고 있던 «남의» 훅 — 보존돼야 한다(양성 대조)
    writeFileSync(join(home, '.claude', 'settings.json'), JSON.stringify({
      hooks: { Stop: [{ matcher: '', hooks: [{ type: 'command', command: "bash '/Users/somebody/my-own-hook.sh'", timeout: 7 }] }] },
    }, null, 2));

    const r = sh([INSTALL_HOOKS, '--home', home]);
    assert.equal(r.code, 0, `머지 실패: ${r.err}`);

    const j = settingsOf(home);
    const evs = Object.keys(j.hooks).sort();
    assert.deepEqual(evs, ['PreToolUse', 'SessionStart', 'Stop', 'UserPromptSubmit'], '4 이벤트가 아니다');

    const cmds = commandsOf(home);
    assert.equal(cmds.filter((c) => c.includes('reply-gate.sh')).length, 1, 'reply-gate.sh 가 1개가 아니다');
    assert.equal(cmds.filter((c) => c.includes('my-own-hook.sh')).length, 1, '사용자의 기존 훅이 사라졌다');
    assert.equal(cmds.filter((c) => c.includes('zzq-never-installed-hook')).length, 0, '미끼가 잡혔다 — 자가 고장났다');

    // 다시 돌려도 쌓이지 않는다
    const before = commandsOf(home).length;
    assert.equal(sh([INSTALL_HOOKS, '--home', home]).code, 0);
    assert.equal(commandsOf(home).length, before, '재실행이 훅을 중복으로 쌓는다');
  });
});

test('H1 — --dry-run 은 파일을 바꾸지 않는다', { skip: skipNoBash }, () => {
  withHome((home) => {
    const p = join(home, '.claude', 'settings.json');
    writeFileSync(p, '{}');
    const r = sh([INSTALL_HOOKS, '--dry-run', '--home', home]);
    assert.equal(r.code, 0);
    assert.match(r.out, /미리보기/);
    assert.equal(read(p), '{}', 'dry-run 이 파일을 바꿨다');
  });
});

// ─────────────────────────────────────────────── H1 --verify 3점 (bash 필요)
test('H1 — --verify: 머지 전 1 → 머지 후 0 → reply-gate 를 지우면 다시 1', { skip: skipNoBash }, () => {
  withHome((home) => {
    // ① 머지 전
    assert.equal(sh([INSTALL_HOOKS, '--verify', '--home', home]).code, 1, '아무것도 없는데 통과했다');

    // ② 머지 후
    assert.equal(sh([INSTALL_HOOKS, '--home', home]).code, 0);
    const ok = sh([INSTALL_HOOKS, '--verify', '--home', home]);
    assert.equal(ok.code, 0, `머지했는데 검사가 실패한다: ${ok.out}`);
    assert.match(ok.out, /검사 통과/);

    // ③ 돌연변이 — reply-gate 행만 지운다. 검사가 이걸 못 잡으면 그 검사는 장식이다.
    const p = join(home, '.claude', 'settings.json');
    const j = JSON.parse(read(p));
    for (const ev of Object.keys(j.hooks)) {
      for (const g of j.hooks[ev]) g.hooks = (g.hooks || []).filter((h) => !h.command.includes('reply-gate.sh'));
    }
    writeFileSync(p, JSON.stringify(j, null, 2));
    const bad = sh([INSTALL_HOOKS, '--verify', '--home', home]);
    assert.equal(bad.code, 1, 'reply-gate 를 지웠는데도 검사가 통과했다 — 검사가 장식이다');
    assert.match(bad.out, /reply-gate\.sh/, '무엇이 빠졌는지 알려주지 않는다');
  });
});

test('H1 — --verify 는 등록됐는데 «파일이 없는» 경우도 잡는다', { skip: skipNoBash }, () => {
  withHome((home) => {
    assert.equal(sh([INSTALL_HOOKS, '--home', home]).code, 0);
    const p = join(home, '.claude', 'settings.json');
    const j = JSON.parse(read(p));
    // 실재하지 않는 경로로 바꿔치기 — 조용한 무반응의 실제 원인 형태
    for (const g of j.hooks.Stop) for (const h of g.hooks) {
      if (h.command.includes('reply-gate.sh')) h.command = "bash '/nowhere/hooks/reply-gate.sh'";
    }
    writeFileSync(p, JSON.stringify(j, null, 2));
    const r = sh([INSTALL_HOOKS, '--verify', '--home', home]);
    assert.equal(r.code, 1, '등록만 돼 있고 파일이 없는데 통과했다');
    assert.match(r.out, /실재하지 않는다/);
  });
});
