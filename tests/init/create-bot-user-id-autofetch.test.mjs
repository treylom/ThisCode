// create-bot Step 4.7 — 사용자 ID 자동 취득 (묻지 않는다)
//
// 왜 이 파일이 있나: 「사용자에게 ID 를 묻지 말라」는 재경님 지시(2026-09-03)는
//   문서 한 줄이라 조용히 되돌아간다. 수동 안내가 다시 «기본»으로 올라오거나,
//   자동 경로가 로그인 비밀값을 만지는 형태로 바뀌는 것 — 둘 다 눈으로는 통과처럼 보인다.
//
// 격리: 게이트의 상태·원장은 전부 임시 디렉터리로 돌린다(사용자의 ~/.thiscode 무접촉).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, readFileSync, existsSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const GATE = join(REPO, 'scripts', 'install-gate.sh');
const SKILL = join(REPO, 'skills', 'create-bot', 'SKILL.md');
const GATE_NAME = 'discord_user_id_autofetch';

// install-gate.test.mjs 와 같은 모양의 모래상자 (헬퍼는 export 돼 있지 않아 형식을 맞춘다)
function withSandbox(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'thiscode-userid-'));
  try {
    return fn({ dir, state: join(dir, 'install-state.yaml'), ledger: join(dir, 'install-log.jsonl') });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function run(box, args, { mode = 'auto' } = {}) {
  writeFileSync(box.state, `install:\n  mode: ${mode}\n`);
  const r = spawnSync('bash', [GATE, ...args], {
    encoding: 'utf8',
    env: { ...process.env, THISCODE_INSTALL_STATE: box.state, THISCODE_INSTALL_LOG: box.ledger },
  });
  return { code: r.status, out: r.stdout ?? '', err: r.stderr ?? '' };
}

// Step 4.7 절만 잘라낸다. 끝 경계는 «다음 `### Step ` 제목»이라 하위 절(### 4.7-b)은 안에 남는다.
function section47() {
  const text = readFileSync(SKILL, 'utf8');
  const start = text.indexOf('### Step 4.7.');
  assert.ok(start >= 0, 'Step 4.7 제목을 못 찾았다 — 문서 구조가 바뀌었다');
  const rest = text.slice(start + 1);
  const m = rest.match(/^### Step /m);
  const body = m ? rest.slice(0, m.index) : rest;
  // 🔴 기대값 게이트: 추출이 빈껍데기면 아래 «0건» 검사들이 «아무것도 안 보고» 통과한다.
  assert.ok(body.length > 500, `Step 4.7 절을 ${body.length}자만 뽑았다 — 경계 정규식이 낡았다`);
  return body;
}

// ─────────────────────────────────────────────── (a) 자동이 기본이다
test('(a) Step 4.7 은 사용자에게 ID 를 「묻지 않고」 자동 취득한다', () => {
  const s = section47();
  assert.match(s, /묻지 않고/, 'ID 를 묻지 않는다는 약속이 문면에서 사라졌다');
  assert.match(s, /자동 취득 \(기본\)/, '자동 취득이 «기본»이라는 표시가 없다');
  assert.ok(s.includes(GATE_NAME), `관문 이름 ${GATE_NAME} 이 절 안에 없다`);
});

// ─────────────────────────────────────────────── (b) 수동은 «뒤»에 온다
// 「수동은 예외」는 문장으로 적으면 안 죽는다 — 위에 절을 하나 끼우면 문장은 그대로고
// 순서만 바뀐다. 그래서 «적힌 말»이 아니라 «실제 위치»를 본다.
test('(b) 수동 절(4.7-b)은 자동 절보다 «뒤»에 있다', () => {
  const text = readFileSync(SKILL, 'utf8');
  const auto = text.indexOf('자동 취득 (기본)');
  const manual = text.indexOf('### 4.7-b');
  assert.ok(auto >= 0, '자동 절을 못 찾았다');
  assert.ok(manual >= 0, '수동 절(### 4.7-b)을 못 찾았다');
  assert.ok(auto < manual, `수동 절이 자동 절보다 앞에 있다 (자동 ${auto} / 수동 ${manual}) — 기본값이 뒤집혔다`);
});

// ─────────────────────────────────────────────── (c) 로그인 비밀값 무접촉
// U3. 「토큰을 출력하지 않는다」가 아니라 «만지지도 않는다»가 계약이다.
// v0.1 의 「페이지 저장소 값으로 직접 호출」 설계는 폐기됐다 — 그 흔적이 되살아나면 여기가 빨개진다.
const FORBIDDEN = ['localStorage', 'Authorization', 'token'];

test('(c) Step 4.7 절에 로그인 비밀값을 만지는 표현이 0 이다 (+ 양성 대조)', () => {
  const s = section47();

  // 양성 대조 1 — 자가 살아 있는지 먼저 보인다. 이게 없으면 아래 0 은
  // 「없어서 0」인지 「안 읽어서 0」인지 구별되지 않는다.
  assert.ok(s.includes('access.json'), '양성 대조 실패 — 절 추출이 실제 본문을 못 잡았다');

  for (const bad of FORBIDDEN) {
    const n = s.split(bad).length - 1;
    assert.equal(n, 0, `Step 4.7 절에 "${bad}" 가 ${n}건 있다 — 로그인 비밀값 무접촉 계약 위반`);
  }

  // 금지문 자체가 살아 있는지
  assert.match(s, /브라우저 저장소·쿠키·인증 헤더 값을 읽거나 만들지 않는다/,
    '비밀값 무접촉 금지문이 사라졌다');
});

test('(c-대조) 금지 문자열 검사기가 장식이 아니다 — 심어놓으면 실제로 잡는다', () => {
  // 위 시험이 «망가진 구현에서도 통과하는 시험»이 아님을 보인다.
  const fake = '이 문장에는 Authorization 헤더와 localStorage 와 token 이 들어 있다.';
  const caught = FORBIDDEN.filter((bad) => fake.split(bad).length - 1 > 0);
  assert.deepEqual(caught, FORBIDDEN, '검사기가 심어둔 금지 문자열을 못 잡는다 = 위 0건은 무의미하다');
});

// ─────────────────────────────────────────────── (d) 미등재 = 시도 강제
// 이 관문은 install.yaml 에 «일부러» 등재하지 않는다. 등재하면 게이트가
// exit 0(= 시도 없이 안내 허용)을 주어 계약이 정반대로 뒤집힌다.
test('(d) 관문은 manual_allowed_without_attempt 에 없고, 게이트는 exit 1 을 준다', () => {
  const yaml = readFileSync(join(REPO, 'configs', 'install.yaml'), 'utf8');

  // 명단 블록만 잘라 이름을 뽑는다 (파일 전체가 아니라 «그 블록»에 없어야 한다)
  const start = yaml.indexOf('manual_allowed_without_attempt:');
  assert.ok(start >= 0, '명단 블록을 못 찾았다 — 계약 파일 구조가 바뀌었다');
  const names = [...yaml.slice(start).matchAll(/^\s*-\s*name:\s*([A-Za-z0-9_]+)/gm)].map((m) => m[1]);
  // 기대값 게이트: 0개면 아래 부재 확인이 «검사 없이» 통과한다.
  assert.ok(names.length >= 6, `명단에서 이름을 ${names.length}개만 뽑았다 — 정규식이 낡았다`);
  assert.ok(names.includes('discord_portal_login'), '양성 대조 — 알려진 등재명이 안 잡힌다');
  assert.ok(!names.includes(GATE_NAME), `${GATE_NAME} 이 명단에 등재됐다 — 시도 없이 수동 안내가 열린다`);

  withSandbox((box) => {
    const r = run(box, [GATE_NAME]);
    assert.equal(r.code, 1, '미등재 관문은 「먼저 한 번 시도할 것」(exit 1)이어야 한다');
    assert.match(r.err, /먼저 자동으로 한 번 시도/);
  });
});

// ─────────────────────────────────────────────── (e) 시도 기록 ↔ 감사
// 게이트의 종료코드는 원장을 «보지 않는다»(2026-09-03 실측). 그래서 「시도했는가」의
// 판정자는 --audit 이다. 아래는 그 축을 기록 전/후로 갈라 확인한다.
test('(e) 시도 기록 전 = 감사 위반 1, 기록 후 = 위반 0', () => {
  withSandbox((box) => {
    // 기록 «전»: 판정만 받고 시도 안 함
    assert.equal(run(box, [GATE_NAME]).code, 1);
    const before = run(box, ['--audit']);
    assert.equal(before.code, 1, '시도 없이 넘어가면 감사가 잡아야 한다');
    assert.match(before.out, new RegExp(`위반 — ${GATE_NAME}`));
    assert.match(before.out, /위반 1 건/);

    // 사유 없는 실패 기록은 거부된다 (사유 없는 수동 낙하 = 계약 위반)
    assert.equal(run(box, ['--attempted', GATE_NAME, 'fail']).code, 2);

    // 사유를 붙여 기록
    const rec = run(box, ['--attempted', GATE_NAME, 'fail', '브라우저 도구가 응답 본문을 안 보여줌']);
    assert.equal(rec.code, 0, '사유가 있으면 실패도 기록된다');

    // 기록 «후»: 위반이 사라진다
    const after = run(box, ['--audit']);
    assert.equal(after.code, 0);
    assert.match(after.out, /위반 0 건/);
  });
});

// 감사 0 을 «계약 준수»로 읽지 않게 한다. --attempted 는 호출자 자기신고이고
// (손석희 독립 검토 R2), 감사는 화면에 안내가 실제로 떴는지 볼 수 없다.
test('(e-한계) 감사 출력은 자기 질문의 한계를 함께 밝힌다', () => {
  withSandbox((box) => {
    run(box, [GATE_NAME]);
    const r = run(box, ['--audit']);
    assert.match(r.out, /수동 안내가 실제로 떴는지는 이 감사로 알 수 없다/);
  });
});
