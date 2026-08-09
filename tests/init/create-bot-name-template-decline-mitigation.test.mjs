// Fix D (2026-08-10, 루돌프 3/3 실측 — 막힘24): selecting "직접 입력" (free text /
// AskUserQuestion's built-in "Other") on the create-bot bot-name question could cancel
// the ENTIRE form ("User declined to answer questions"), losing both the name answer
// AND whatever other question had been bundled into the same AskUserQuestion call
// (observed: name + soul-template selection together). Investigation found zero
// ThisCode code touching AskUserQuestion's decline/"Other" handling — that mechanism
// lives entirely in the host tool, outside this repo — so this is judged a framework-
// level issue, NOT a contained bug fixable in ThisCode's own code (판정 채택 그대로).
// The mitigation shipped here is intentionally NOT a root-cause fix: (1) keep Step 1
// (name) and Step 5 (template) as separate AskUserQuestion calls so a decline on one
// can't drag the other down with it (reduces blast radius, does not prevent the
// decline itself), and (2) document a plain-text workaround for when a form does die.
// SKILL.md is prose, not executable code, so these are existence+behavior (2-slot)
// checks — existence of the mitigation text, and position/cross-reference correctness.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

function readSkill() {
  return readFileSync('skills/create-bot/SKILL.md', 'utf8').replace(/\r\n/g, '\n');
}

test('Fix D: Step 1 mandates a separate AskUserQuestion call from Step 5, and is honest that this is a mitigation, not a root-cause fix', () => {
  const text = readSkill();
  const step1Idx = text.indexOf('### Step 1. 봇 이름 입력 (AskUserQuestion)');
  const mitigationIdx = text.indexOf('막힘24 완화');
  const step2Idx = text.indexOf('### Step 2. 봇 디렉토리 생성');
  assert.ok(step1Idx > -1 && mitigationIdx > -1 && step2Idx > -1, 'Step 1, the mitigation paragraph, and Step 2 must all exist');
  assert.ok(step1Idx < mitigationIdx && mitigationIdx < step2Idx, 'the mitigation paragraph must sit inside Step 1, before Step 2');

  const mitigationBlock = text.slice(mitigationIdx, step2Idx).replace(/\*\*/g, '');
  assert.match(mitigationBlock, /반드시 Step 5\(soul\.md 템플릿 선택\)와 별도의 AskUserQuestion 호출로/, 'must mandate Step 1 and Step 5 run as separate AskUserQuestion calls');
  assert.match(mitigationBlock, /근본 수리 불가|root fix 아님/, 'must NOT overclaim this as a root-cause fix — this is documented as a blast-radius mitigation only (no phantom fix)');
});

test('Fix D: Step 5 cross-references Step 1\'s separate-call mandate (not a silent, one-sided constraint)', () => {
  const text = readSkill();
  const step5Idx = text.indexOf('### Step 5. soul.md template 선택 + 채우기');
  const pointerIdx = text.indexOf('Step 1 과 별도 호출');
  const tableIdx = text.indexOf('| template | 적합 |');
  assert.ok(step5Idx > -1 && pointerIdx > -1 && tableIdx > -1, 'Step 5 header, the cross-reference pointer, and the template table must all exist');
  assert.ok(step5Idx < pointerIdx && pointerIdx < tableIdx, 'the pointer must sit at the top of Step 5, before the template table');
});

test('Fix D: a plain-text fallback is documented for when the form dies (workaround, not a fix)', () => {
  const text = readSkill();
  const workaroundIdx = text.indexOf('폼이 죽으면 평문으로 우회');
  assert.ok(workaroundIdx > -1, 'the plain-text fallback paragraph must exist');
  const workaroundBlock = text.slice(workaroundIdx, workaroundIdx + 600).replace(/\*\*/g, '');
  assert.match(workaroundBlock, /평문 문장으로 답을 달라/, 'must instruct asking for a plain-text sentence answer instead of re-prompting with clickable options');
  assert.match(workaroundBlock, /호스트 프레임워크 층/, 'must state this is a host-framework-level issue, honest about scope (not claiming ThisCode code fixed it)');
});
