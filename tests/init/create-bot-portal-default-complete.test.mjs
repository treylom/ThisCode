// B7 (재경님 2026-08-10 결정): "캡차·사람 관문 직전까지는 알아서 전부 다 하는 것까지가
// 우리 설치기 역할." The create-bot wizard's Discord Developer Portal section used to print
// instructions and stop; the fix promotes an already-working capability (drive the portal via
// whatever browser-automation tool the session has, per the same detection pattern
// skills/help/SKILL.md STEP 2.5 already uses) to the DEFAULT path — no upfront "should I do this
// for you?" question (that's the slack-configure pattern this explicitly does NOT copy), and only
// two real human gates (hCaptcha, password/MFA modal) still pause the flow. skills/create-bot/SKILL.md
// is prose, not executable code, so these are existence+behavior regex locks, same style as the
// B3/B4 test file.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

function readSkill() {
  return readFileSync('skills/create-bot/SKILL.md', 'utf8').replace(/\r\n/g, '\n');
}

test('B7: Step 3 declares default = wizard completes the portal itself, not print-and-stop', () => {
  const text = readSkill();
  assert.match(text, /### Step 3\. Discord 봇 생성 \(Developer Portal — 기본값 = 마법사가 완주, B7\)/);
  assert.match(text, /묻지 않고 기본으로 진행/, 'the default must not ask permission first (unlike slack-configure)');
});

test('B7: exactly two hard human gates remain (hCaptcha, password/MFA) — the old 4-gate table is gone', () => {
  const text = readSkill();
  assert.match(text, /하드 인간 관문 — 정확히 2개 지점/);
  assert.match(text, /hCaptcha 가 뜨면 여기서 멈춘다/);
  assert.match(text, /비밀번호\/다단계 인증 모달이 뜨면 여기서 멈춘다/);
  assert.doesNotMatch(
    text,
    /사람이 반드시 직접 눌러야 하는 자리가 4곳/,
    'the superseded "4 hard gates" framing must not linger alongside the new 2-gate contract',
  );
});

test('B7: the default flow is narrated in first person ("지금 ~합니다"), not phrased as commands to the user', () => {
  const text = readSkill();
  const flowStart = text.indexOf('**기본 흐름 (도구 있음, 기본값)');
  assert.ok(flowStart > -1, 'the default-flow section must exist');
  const flowEnd = text.indexOf('완료 후', flowStart);
  const flowBlock = text.slice(flowStart, flowEnd);
  assert.match(flowBlock, /지금 ~합니다" 서술만/, 'the narration rule must be stated inline');
  // sample first-person narration lines actually present in the block
  assert.match(flowBlock, /"Discord 개발자 포털을 엽니다\."/);
  assert.match(flowBlock, /"봇을 서버에 초대합니다\."/);
});

test('B7: tool-availability detection gates the default vs. manual-fallback branch (no new hand-rolled automation — reuses the help-skill detection principle)', () => {
  const text = readSkill();
  assert.match(text, /가용성 탐지/);
  assert.match(text, /`\/thiscode:help` STEP 2\.5 와 동일 원칙/, 'must reuse the existing detection pattern, not invent a new one');
  assert.match(text, /\*\*수동 안내 \(도구 없음/, 'a manual fallback branch must still exist for sessions with no browser automation');
});

test('B7: commands/start.md points Step 2 at create-bot Step 3 as canonical instead of holding its own full copy', () => {
  const text = readFileSync('commands/start.md', 'utf8');
  assert.match(text, /### Step 2\. Discord 봇 생성 \(기본 = 자동 완주, B7\)/);
  assert.match(text, /`skills\/create-bot\/SKILL\.md` Step 3 이 정본이다/);
});

test('B7: skills/help/SKILL.md no longer asserts that app creation/token issuance must always be done by a human', () => {
  const text = readFileSync('skills/help/SKILL.md', 'utf8');
  assert.doesNotMatch(
    text,
    /앱 생성·봇 토큰 발급은 원리상 사람이 직접 해야 한다/,
    'this claim is false after B7 — create-bot now completes the portal by default',
  );
  assert.match(text, /B7 이후는 아니다/);
});
