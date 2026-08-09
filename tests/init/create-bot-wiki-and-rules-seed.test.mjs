// B3+B4 (PRD 59-pm-prd-night-batch, ThisCodex parity commit 1dc6fc5): the
// wiki (Obsidian vault) path question and the rules-seed.md copy-once
// install are authored into skills/create-bot/SKILL.md, which is a
// Claude-guided instruction document, not executable code — bin/thiscode.mjs
// has no bot-creation manifest (install/thiscode.install.json only installs
// the ThisCode harness itself). These regex assertions are the two-slot
// self-check ("existence" + "behavior") applied to prose: they lock the
// question's position in the interview order and the explicit blank-answer
// branch, not runtime behavior (there is none to run).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

function readSkill() {
  return readFileSync('skills/create-bot/SKILL.md', 'utf8').replace(/\r\n/g, '\n');
}

test('B4: the wiki path question is a first-class step, asked before WD/CLAUDE.md is finalized', () => {
  const text = readSkill();
  const wikiStepIdx = text.indexOf('### Step 5.7');
  const step6Idx = text.indexOf('### Step 6.');
  assert.ok(wikiStepIdx > -1, 'Step 5.7 (wiki path question) must exist');
  assert.ok(step6Idx > -1, 'Step 6 (WD/CLAUDE.md) must exist');
  assert.ok(wikiStepIdx < step6Idx, 'the wiki path question must precede WD/CLAUDE.md finalization (Step 6)');
  assert.match(text, /옵시디언 위키\(vault\) 경로/, 'the question must name the wiki/vault path');
  assert.match(text, /선택 사항/, 'the question must state it is optional');
});

test('B4: a blank wiki path answer is an explicit non-blocking branch, not a silent default', () => {
  const text = readSkill();
  assert.match(text, /빈 값 = 생성 계속/, 'blank answer must explicitly continue bot creation');
  assert.match(text, /샘플 위키/, 'the no-path branch must mention starting from a sample wiki');
});

test('B4: a given wiki path lands read/write targets in CLAUDE.md and THISCODE_WIKI_PATH at launch', () => {
  const text = readSkill();
  assert.match(text, /##\s*위키 연결/, 'CLAUDE.md must gain a wiki-connection section');
  assert.match(text, /읽기 대상/);
  assert.match(text, /쓰기 대상/);
  assert.match(text, /THISCODE_WIKI_PATH/, 'the launch instructions must export THISCODE_WIKI_PATH when a path was given');
});

test('B3: rules-seed.md is copied once into the bot WD and the copy is never overwritten', () => {
  const text = readSkill();
  assert.match(text, /rules-seed\.md/);
  assert.match(text, /\[ ! -f "\$WD\/rules-seed\.md" \]/, 'the copy must be gated on the destination not already existing (copy-once)');
  assert.match(text, /절대 (건드리지 않는다|덮어쓰지 않음)/, 'the never-overwrite contract must be stated explicitly');
});

test('B3: the generated CLAUDE.md references rules-seed.md', () => {
  const text = readSkill();
  const claudeMdBlockStart = text.indexOf('```markdown\n# <bot-name> WD');
  assert.ok(claudeMdBlockStart > -1, 'the CLAUDE.md template block must exist');
  const claudeMdBlockEnd = text.indexOf('```', claudeMdBlockStart + 10);
  const claudeMdBlock = text.slice(claudeMdBlockStart, claudeMdBlockEnd);
  assert.match(claudeMdBlock, /rules-seed\.md/, 'the CLAUDE.md template itself must point at rules-seed.md');
});

test('B3 (기준 4-5): a staleness WARN is documented at the actual boot checkpoint (SessionStart hook)', () => {
  const text = readSkill();
  assert.match(text, /bot-session-init\.sh/);
  assert.match(text, /\[thiscode\]\[WARN\] rules-seed vX -> vY available — update by explicit command only/);
});

test('templates/rules-seed.md exists with the v1.0.0 stamp, both rules, and the Slack-only DM caveat (parity with ThisCodex examples/rules-seed.md)', () => {
  const text = readFileSync('templates/rules-seed.md', 'utf8');
  assert.match(text, /^<!-- rules-seed v1\.0\.0 -->/);
  assert.match(text, /## Rule 1/);
  assert.match(text, /Slack DM 한정/, 'Rule 1 must scope the thread_ts echo rule to the Slack bridge');
  assert.match(text, /## Rule 2/);
  assert.match(text, /위키.*저장|저장.*위키/, 'Rule 2 must state the wiki save policy');
  assert.match(text, /THISCODE_WIKI_PATH/);
});
