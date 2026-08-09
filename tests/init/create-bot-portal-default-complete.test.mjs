// B7 (재경님 2026-08-10 결정): "캡차·사람 관문 직전까지는 알아서 전부 다 하는 것까지가
// 우리 설치기 역할." The create-bot wizard's Discord Developer Portal section used to print
// instructions and stop; the fix promotes an already-working capability (drive the portal via
// whatever browser-automation tool the session has, per the same detection pattern
// skills/help/SKILL.md STEP 2.5 already uses) to the DEFAULT path — no upfront "should I do this
// for you?" question (that's the slack-configure pattern this explicitly does NOT copy). Three
// real human gates still pause the flow (revised from an initial 2-gate cut — 글재경's 2026-08-10
// review ④ caught that a clean/re-shoot account's actual first screen is a login wall, which the
// original table never declared a branch for): portal login (credentials+MFA), hCaptcha, and the
// Reset Token password/MFA modal. skills/create-bot/SKILL.md is prose, not executable code, so
// these are existence+behavior regex locks, same style as the B3/B4 test file.
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

test('B7 (④ revision): exactly three hard human gates remain (login, hCaptcha, password/MFA) — both the old 4-gate and the interim 2-gate tables are gone', () => {
  const text = readSkill();
  assert.match(text, /하드 인간 관문 — 정확히 3곳/);
  assert.match(text, /로그인 화면이면 여기서 멈춘다/, 'the portal-login branch (④ fix) must exist — a clean account\'s first screen is a login wall');
  assert.match(text, /하드 관문 1, ④/);
  assert.match(text, /hCaptcha 가 뜨면 여기서 멈춘다.*하드 관문 2\)|하드 관문 2\).*hCaptcha 가 뜨면 여기서 멈춘다/s);
  assert.match(text, /비밀번호\/다단계 인증 모달이 뜨면 여기서 멈춘다.*하드 관문 3\)/s);
  assert.doesNotMatch(
    text,
    /사람이 반드시 직접 눌러야 하는 자리가 4곳/,
    'the superseded original "4 hard gates" framing must not linger',
  );
  assert.doesNotMatch(
    text,
    /하드 인간 관문 — 정확히 2개 지점/,
    'the interim 2-gate table (missing the login branch) must not linger alongside the 3-gate contract',
  );
});

test('B7 (④): the login branch sits between step 1 (open portal) and step 2 (New Application) — before the flow assumed an already-logged-in session', () => {
  const text = readSkill();
  const step1Idx = text.indexOf('1. `https://discord.com/developers/applications` 로 이동');
  const loginBranchIdx = text.indexOf('로그인 화면이면 여기서 멈춘다');
  const step2Idx = text.indexOf('2. "New Application" 클릭');
  assert.ok(step1Idx > -1 && loginBranchIdx > -1 && step2Idx > -1, 'step 1, the login branch, and step 2 must all exist');
  assert.ok(step1Idx < loginBranchIdx && loginBranchIdx < step2Idx, 'the login branch must sit between opening the portal and creating the application');
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

// Fix C (2026-08-10, 카파시 root-cause + 루돌프 실측): Step 3's header claimed
// "printing instructions and stopping is a defect in the default flow", but the
// very next "가용성 탐지" branch said the opposite for the no-tool case — "not a
// defect, an environment limit" — and a freshly-installed session has NO
// browser automation by default, so most students landed exactly in that
// branch. B7's "default completes" promise was false on a clean install. The
// fix material already existed in skills/help/SKILL.md STEP 2.5 point 2 (offer
// to attach playwright MCP, human approval gate kept) — reused verbatim rather
// than inventing new automation. Existence+behavior 2-slot check: the offer
// text exists (existence) AND sits in an approve/decline branch where only
// decline reaches the "environment limit" label and only approve rejoins the
// default flow (behavior/position).
test('B7 (Fix C): the "no tool" branch offers to attach playwright MCP (help:2.5 wording reused verbatim) instead of falling straight back to manual guidance', () => {
  const text = readSkill();
  const helpText = readFileSync('skills/help/SKILL.md', 'utf8');
  const offerLine = '브라우저를 같이 볼 수 있는 도구를 1분 안에 붙일 수 있어요. 붙일까요?';
  const attachCmd = 'claude mcp add playwright -- npx @playwright/mcp@latest';
  assert.ok(helpText.includes(offerLine), 'sanity: the offer text must still exist verbatim in help:2.5 (the source being reused)');
  assert.ok(text.includes(offerLine), 'create-bot must reuse the exact help:2.5 offer wording, not paraphrase or invent new copy');
  assert.ok(text.includes(attachCmd), 'create-bot must reuse the exact help:2.5 attach command');

  const noToolIdx = text.indexOf('**없으면**');
  const offerIdx = text.indexOf(offerLine);
  const approveIdx = text.indexOf('**승인하면**');
  const declineIdx = text.indexOf('**거부할 때만**');
  assert.ok(
    [noToolIdx, offerIdx, approveIdx, declineIdx].every((i) => i > -1),
    'the no-tool branch, the offer, and both the approve and decline sub-branches must all exist',
  );
  assert.ok(
    noToolIdx < offerIdx && offerIdx < approveIdx && approveIdx < declineIdx,
    'order must be: no-tool branch → offer → approve sub-branch → decline sub-branch',
  );

  const approveBlock = text.slice(approveIdx, declineIdx);
  assert.match(approveBlock, /재탐지.*기본 흐름을 그대로 실행/, 'approving must rejoin the default flow — B7 still completes');

  const declineBlock = text.slice(declineIdx, text.indexOf('### Step 4.', declineIdx));
  assert.match(declineBlock, /결함이 아니라 환경 한계/, 'the "not a defect, an environment limit" label must be scoped to the decline sub-branch');

  // regression lock: the OLD unscoped label (applied to the whole no-tool
  // branch regardless of whether an offer was even made) must not reappear.
  assert.doesNotMatch(
    text,
    /없으면\*\* → 새 도구 설치를 여기서 강요하지 않는다.*이건 결함이 아니라 환경 한계다/s,
    'the old unconditional "not a defect" framing (skipping the playwright offer entirely) must not reappear',
  );
});

// 🟡C-a (2026-08-10, 글재경 재검토 지시): Fix C reused help.md STEP 2.5's playwright-MCP
// offer verbatim in create-bot rather than pointing at a shared source (SKILL.md is prose,
// not executable, so there's no import mechanism — see the copy-coherence note in Fix C's
// commit). That makes it an intentional DUAL COPY, not a copy-asymmetry: whichever file
// changes first, the other must follow or the two silently disagree. This is a dedicated
// machine check for that — it extracts the two shared literals from EACH file independently
// and asserts they are byte-identical to EACH OTHER (not to a third hardcoded string in this
// test, which would only catch one file drifting from the test, not the two files drifting
// from each other while both still happen to match some independent literal).
test('🟡C-a: the playwright-attach offer text and command stay byte-identical between create-bot and help.md (drift guard)', () => {
  const createBotText = readSkill();
  const helpText = readFileSync('skills/help/SKILL.md', 'utf8');

  const attachRe = /`(claude mcp add playwright[^`]*)`/;
  const createBotAttach = createBotText.match(attachRe)?.[1];
  const helpAttach = helpText.match(attachRe)?.[1];
  assert.ok(createBotAttach, 'create-bot must contain a backtick-quoted playwright attach command');
  assert.ok(helpAttach, 'help.md must contain a backtick-quoted playwright attach command');
  assert.equal(createBotAttach, helpAttach, 'the attach command must be identical between create-bot and help.md — a drift here (e.g. one side bumping the npx package spec) would silently break the reused suggestion');

  const offerRe = /"(브라우저를 같이 볼 수 있는[^"]*)"/;
  const createBotOffer = createBotText.match(offerRe)?.[1];
  const helpOffer = helpText.match(offerRe)?.[1];
  assert.ok(createBotOffer, 'create-bot must contain the quoted offer sentence');
  assert.ok(helpOffer, 'help.md must contain the quoted offer sentence');
  assert.equal(createBotOffer, helpOffer, 'the offer sentence must be identical between create-bot and help.md');
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
