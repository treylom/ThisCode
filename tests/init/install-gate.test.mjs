// install-gate.sh — 설치 자동화 계약 게이트 (R2·R4)
//
// 왜 이 파일이 있나: 이 게이트의 시험 「8/8」이 2026-08-13 최초 배선 때는
//   «그때 손으로 돌린 것»이었다. 손으로 돌린 통과는 재현되지 않고 회귀도 못 막는다.
//   특히 이 게이트의 핵심 방어(접두사 누출)는 눈으로 보면 통과처럼 보이는 종류라
//   기계가 잡아야 한다.
//
// 격리: 상태·원장 경로를 전부 임시 디렉터리로 돌린다. 사용자의 실제
//   ~/.thiscode/ 를 건드리면 시험이 환경을 오염시키고, 반대로 환경이 시험을 오염시킨다.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const GATE = join(REPO, 'scripts', 'install-gate.sh');

function withSandbox(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'thiscode-gate-'));
  try {
    return fn({
      dir,
      state: join(dir, 'install-state.yaml'),
      ledger: join(dir, 'install-log.jsonl'),
    });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function run(box, args, { mode, gateScript = GATE } = {}) {
  if (mode) writeFileSync(box.state, `install:\n  mode: ${mode}\n`);
  const r = spawnSync('bash', [gateScript, ...args], {
    encoding: 'utf8',
    env: {
      ...process.env,
      THISCODE_INSTALL_STATE: box.state,
      THISCODE_INSTALL_LOG: box.ledger,
    },
  });
  return { code: r.status, out: r.stdout ?? '', err: r.stderr ?? '' };
}

// 계약 파일을 갈아끼운 «가짜 레포»를 만든다. 스크립트가 CONFIG 를 형제 디렉터리로
// 찾으므로, 스크립트를 복사한 자리 옆에 configs/install.yaml 을 두면 그게 계약이 된다.
function fakeRepo(box, configText) {
  const scripts = join(box.dir, 'fake', 'scripts');
  const configs = join(box.dir, 'fake', 'configs');
  mkdirSync(scripts, { recursive: true });
  if (configText !== null) {
    mkdirSync(configs, { recursive: true });
    writeFileSync(join(configs, 'install.yaml'), configText);
  }
  const copy = join(scripts, 'install-gate.sh');
  writeFileSync(copy, readFileSync(GATE, 'utf8'));
  return copy;
}

function ledger(box) {
  if (!existsSync(box.ledger)) return [];
  return readFileSync(box.ledger, 'utf8')
    .split('\n')
    .filter(Boolean)
    .map((l) => JSON.parse(l));
}

// ─────────────────────────────────────────────── 종료코드 계약 (불변)
// commands/start.md 의 계약표와 skills/create-bot/SKILL.md 가 이 숫자에 걸려 있다.
// 바뀌면 그 두 문서가 «조용히» 거짓이 된다.

test('등재된 관문 → exit 0 (시도 없이 안내해도 되는 유일한 지점)', () => {
  withSandbox((box) => {
    for (const g of ['discord_hcaptcha', 'discord_portal_login', 'slack_token_paste']) {
      const r = run(box, [g], { mode: 'auto' });
      assert.equal(r.code, 0, `${g} 은 계약 명단에 있으므로 0 이어야 한다`);
    }
  });
});

test('미등재 관문 → exit 1 (먼저 한 번 시도할 것)', () => {
  withSandbox((box) => {
    const r = run(box, ['some_new_gate_nobody_declared'], { mode: 'auto' });
    assert.equal(r.code, 1);
    assert.match(r.err, /먼저 자동으로 한 번 시도/);
  });
});

test('인자 없음 → exit 2', () => {
  withSandbox((box) => {
    assert.equal(run(box, [], { mode: 'auto' }).code, 2);
  });
});

test('manual 모드는 미등재 관문도 안내 허용 (사용자가 직접 하겠다고 골랐다)', () => {
  withSandbox((box) => {
    const r = run(box, ['some_new_gate_nobody_declared'], { mode: 'manual' });
    assert.equal(r.code, 0);
    assert.match(r.out, /manual 모드/);
  });
});

// 🔴 이 게이트의 핵심 방어 = 이름 «완전 일치»(grep -qx).
//
// 2026-08-13 돌연변이 시험에서 배운 것: -qx 를 -q 로 망가뜨렸을 때
//   ㉠ 「등재명 + 접미사」(discord_hcaptcha_v2)  → 망가진 코드에서도 여전히 exit 1
//   ㉡ 「등재명의 잘린 형태」(discord_hcaptch)   → 망가진 코드에서 exit 0 (누출)
// 즉 ㉠ 만 시험하면 «망가진 구현에서도 통과하는 시험» = 장식이다.
// 방향이 둘인 이유: 검사가 「GATE 가 명단 텍스트 안에 있나」라서, 위험은
// GATE 가 등재명의 «부분»일 때만 생긴다. 그래서 아래 두 시험은 역할이 다르다.

test('㉠ 등재명 + 접미사는 별개 관문이다 (참이지만 완전일치 방어를 시험하지는 않는다)', () => {
  withSandbox((box) => {
    for (const g of ['discord_hcaptcha_v2', 'discord_portal_login_sso']) {
      assert.equal(run(box, [g], { mode: 'auto' }).code, 1, `${g} 는 별개 관문이다`);
    }
  });
});

test('㉡ 누출 차단 — 등재명의 «잘린» 형태는 통과 못 한다 (완전일치가 깨지면 여기가 빨개진다)', () => {
  withSandbox((box) => {
    assert.equal(run(box, ['discord_hcaptch'], { mode: 'auto' }).code, 1);
  });
});

// ㉡ 의 실전형: 명단이 «긴 이름만» 들고 있는데 짧은 이름으로 물어보는 경우.
// 부분 일치 구현이면 짧은 이름(미등재!)이 긴 등재명에 묻어 통과한다 — 실제로
// 명단에 `discord_hcaptcha_v2` 를 추가하고 옛 이름을 지우면 바로 생기는 상황이다.
test('㉡-실전 — 명단에 긴 이름만 있을 때 짧은 미등재 이름이 묻어 통과하지 않는다', () => {
  withSandbox((box) => {
    const script = fakeRepo(box, [
      'install:',
      '  default_mode: auto',
      '  manual_allowed_without_attempt:',
      '    - name: discord_hcaptcha_v2',
      '      reason: 봇 감지 캡차 — 우회 금지',
      '',
    ].join('\n'));
    assert.equal(run(box, ['discord_hcaptcha_v2'], { mode: 'auto', gateScript: script }).code, 0,
      '등재된 긴 이름 자체는 허용');
    assert.equal(run(box, ['discord_hcaptcha'], { mode: 'auto', gateScript: script }).code, 1,
      '짧은 이름은 명단에 없다 — 긴 이름에 묻어 통과하면 안 된다');
  });
});

test('계약 파일이 없으면 exit 2 — 모르면 통과가 아니라 시도 쪽으로 떨어진다', () => {
  withSandbox((box) => {
    const r = run(box, ['discord_hcaptcha'], { mode: 'auto', gateScript: fakeRepo(box, null) });
    assert.equal(r.code, 2, '계약 파일 부재는 통과(0)가 아니다');
    assert.match(r.err, /계약 파일 없음/);
  });
});

// ─────────────────────────────────────────────── 원장 (R2 합격 기준의 판정 수단)
// 01-spec.md:23 = 「자동 시도 1회 + 그 결과 기록. 시도 없이 안내 = FAIL」
// 기록이 없으면 그 기준은 판정 불가다.

test('게이트 호출은 원장에 남는다', () => {
  withSandbox((box) => {
    run(box, ['discord_hcaptcha'], { mode: 'auto' });
    run(box, ['brand_new_gate'], { mode: 'auto' });
    const rows = ledger(box);
    assert.equal(rows.length, 2);
    assert.equal(rows[0].result, 'allowed');
    assert.equal(rows[1].result, 'attempt-required');
    assert.equal(rows[1].gate, 'brand_new_gate');
  });
});

test('--attempted 로 시도 사실을 남길 수 있다', () => {
  withSandbox((box) => {
    const r = run(box, ['--attempted', 'brand_new_gate', 'ok'], { mode: 'auto' });
    assert.equal(r.code, 0);
    const rows = ledger(box).filter((x) => x.kind === 'attempt');
    assert.equal(rows.length, 1);
    assert.equal(rows[0].result, 'ok');
  });
});

test('실패를 «사유 없이» 기록하려 하면 거부한다 — 사유 없는 수동 낙하는 계약 위반', () => {
  withSandbox((box) => {
    const r = run(box, ['--attempted', 'brand_new_gate', 'fail'], { mode: 'auto' });
    assert.equal(r.code, 2);
    assert.equal(ledger(box).filter((x) => x.kind === 'attempt').length, 0, '거부했으면 기록도 없어야 한다');
  });
});

test('사유가 있으면 실패도 기록된다 (그리고 사유가 원장에 실린다)', () => {
  withSandbox((box) => {
    const r = run(box, ['--attempted', 'brand_new_gate', 'fail', '브라우저 도구 설치가 네트워크에서 실패'], { mode: 'auto' });
    assert.equal(r.code, 0);
    const row = ledger(box).find((x) => x.kind === 'attempt');
    assert.equal(row.result, 'fail');
    assert.match(row.detail, /네트워크/);
  });
});

test('--audit: 「시도하라」 판정만 있고 시도 기록이 없으면 위반으로 잡는다', () => {
  withSandbox((box) => {
    run(box, ['brand_new_gate'], { mode: 'auto' });      // exit 1 판정만 남기고 시도 안 함
    const r = run(box, ['--audit'], { mode: 'auto' });
    assert.equal(r.code, 1, '위반이 있으면 exit 1');
    assert.match(r.out, /위반 — brand_new_gate/);
    assert.match(r.out, /위반 1 건/);
  });
});

test('--audit: 시도를 기록하면 위반이 사라진다', () => {
  withSandbox((box) => {
    run(box, ['brand_new_gate'], { mode: 'auto' });
    run(box, ['--attempted', 'brand_new_gate', 'fail', '자격증명 없이는 진행 불가'], { mode: 'auto' });
    const r = run(box, ['--audit'], { mode: 'auto' });
    assert.equal(r.code, 0);
    assert.match(r.out, /위반 0 건/);
  });
});

test('--audit: 시도가 «판정보다 먼저» 있었으면 그건 이번 판정에 대한 시도가 아니다', () => {
  withSandbox((box) => {
    run(box, ['--attempted', 'brand_new_gate', 'ok'], { mode: 'auto' });   // 옛 시도
    run(box, ['brand_new_gate'], { mode: 'auto' });                        // 그 뒤에 새 판정
    const r = run(box, ['--audit'], { mode: 'auto' });
    assert.equal(r.code, 1, '옛 시도로 새 판정을 갚을 수 없다');
  });
});

// 감사가 «답하지 않는» 것을 감사 스스로 말하게 한다.
// 위반 0 을 「계약 준수」로 읽으면 안 되기 때문이다 — 게이트는 화면을 못 본다.
test('--audit 출력은 자기 질문의 한계를 함께 밝힌다', () => {
  withSandbox((box) => {
    run(box, ['discord_hcaptcha'], { mode: 'auto' });
    const r = run(box, ['--audit'], { mode: 'auto' });
    assert.match(r.out, /감사 질문:/);
    assert.match(r.out, /수동 안내가 실제로 떴는지는 이 감사로 알 수 없다/);
  });
});

test('원장이 없어도 --audit 은 깨지지 않는다', () => {
  withSandbox((box) => {
    const r = run(box, ['--audit'], { mode: 'auto' });
    assert.equal(r.code, 0);
    assert.match(r.out, /원장 없음/);
  });
});

// ─────────────────────────────────────────────── 문서 ↔ 계약 정합
// 스킬 문서가 「이 이름은 exit 0 이다」라고 «적어» 두면, 그 문장은 계약 파일이
// 바뀌어도 안 죽는다. 주석이 정본을 참칭하는 형태다 — 그래서 문서에 적힌 이름을
// 실제로 게이트에 물어본다. 표를 고치고 명단을 안 고치면(또는 반대) 여기가 빨개진다.

function namesFromTable(file, rowRe) {
  const text = readFileSync(join(REPO, file), 'utf8');
  const out = [];
  for (const line of text.split('\n')) {
    const m = line.match(rowRe);
    if (m) out.push(m[1]);
  }
  return out;
}

test('slack-configure 관문 표에 적힌 이름은 실제로 게이트가 exit 0 을 준다', () => {
  const names = namesFromTable(
    join('skills', 'slack-configure', 'SKILL.md'),
    /^\|\s*[A-E]\s*\|[^|]*\|\s*`([a-z_]+)`\s*\|\s*exit 0\s*\|/,
  );
  // 🔴 기대값 게이트: 추출이 0건이면 아래 for 문이 «아무것도 검사하지 않고» 통과한다.
  //    표 형식이 바뀌어 정규식이 빗나가는 순간이 정확히 그 상황이다.
  assert.ok(names.length >= 6, `관문 표에서 이름을 ${names.length}개만 뽑았다 — 표 형식이 바뀌었거나 정규식이 낡았다`);
  withSandbox((box) => {
    for (const n of names) {
      assert.equal(run(box, [n], { mode: 'auto' }).code, 0,
        `${n} 은 문서가 exit 0 이라 적어놨는데 계약 명단에 없다`);
    }
  });
});

test('create-bot 하드 관문 3곳의 계약상 이름도 실제로 exit 0 이다', () => {
  const text = readFileSync(join(REPO, 'skills', 'create-bot', 'SKILL.md'), 'utf8');
  const names = [...text.matchAll(/\b([1-3])\s*=\s*`(discord_[a-z_]+)`/g)].map((m) => m[2]);
  assert.equal(names.length, 3, `하드 관문 이름을 ${names.length}개 뽑았다 — 3개여야 한다`);
  withSandbox((box) => {
    for (const n of names) {
      assert.equal(run(box, [n], { mode: 'auto' }).code, 0, `${n} 은 등재돼 있어야 한다`);
    }
  });
});

// 반대 방향: 명단에 «없는» 이름을 문서가 exit 0 이라 적으면 위 시험이 잡는다.
// 그 시험이 진짜로 잡는지(= 장식이 아닌지)를 여기서 확인한다 — 돌연변이 대신
// 「명단에 절대 없을 이름」을 직접 물어 자가 살아 있음을 보인다.
test('명단에 없는 이름은 exit 0 을 못 받는다 (위 두 시험이 장식이 아님을 보이는 대조군)', () => {
  withSandbox((box) => {
    assert.equal(run(box, ['slack_channel_id_lookup'], { mode: 'auto' }).code, 1);
    assert.equal(run(box, ['discord_oauth_url_build'], { mode: 'auto' }).code, 1);
  });
});
