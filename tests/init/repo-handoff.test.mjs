// Spec 2026-05-18-repo-handoff-interactive-default §4.3 (ThisCode harden/align).
// ThisCode is already wizard-default; the recurrence gap is that the contract
// is not stated at the entry. Lock: SKILL.md carries the shared contract block,
// and the shared contract file is bundled. RED before the harden, GREEN after.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const skill = readFileSync(new URL('../../skills/init/SKILL.md', import.meta.url), 'utf8');
const contract = readFileSync(
  new URL('../../contracts/repo-handoff-install-contract.md', import.meta.url),
  'utf8',
);
const readme = readFileSync(new URL('../../README.md', import.meta.url), 'utf8');

// A1-equivalent (recurrence prevention): entry skill states the contract at top.
test('init SKILL.md states the repo-handoff contract: default interactive', () => {
  assert.match(
    skill,
    /default.*interactive|기본.*대화형|interactive guided/i,
    'SKILL.md must state interactive guided is the default',
  );
});

test('init SKILL.md instructs AI agents to relay questions, not self-answer', () => {
  assert.match(
    skill,
    /relay|중계|ask the user|사용자에게 (묻|질문)/i,
    'SKILL.md must instruct relaying questions to the user',
  );
  assert.match(
    skill,
    /not .*(self-answer|fabricate|auto-run|자문자답|스스로 답)|self-answer/i,
    'SKILL.md must forbid self-answering / auto-run non-interactive',
  );
});

test('init SKILL.md forbids reporting copied = installed', () => {
  assert.match(
    skill,
    /not .*(report|claim).*(install|onboard)|복사.*설치.*아님|placement is not (guided|onboarding)|copied.*=.*installed/i,
    'SKILL.md must forbid placement-as-completed-onboarding',
  );
});

test('init SKILL.md scopes non-interactive to explicit opt-out only', () => {
  assert.match(
    skill,
    /non-interactive.*only|only .*non-interactive|명시.*옵트아웃|explicit.*opt-?out|CI.*자동화|CI \/ automation/i,
    'SKILL.md must scope non-interactive to explicit opt-out / CI',
  );
});

// Shared contract bundled (spec §8 / porting-infra §2).
test('shared repo-handoff contract is bundled with the 4 normative points', () => {
  // whitespace-tolerant: markdown wraps multi-word phrases across lines.
  assert.match(contract, /Default\s*=\s*interactive\s+guided/i, 'point 1 missing');
  assert.match(contract, /Non-interactive\s+only\s+on\s+explicit\s+opt-out/i, 'point 2 missing');
  assert.match(contract, /relay\s+each\s+question\s+to\s+the\s+user/i, 'point 3 missing');
  assert.match(contract, /safe-stop/i, 'point 4 missing');
});

// A8 (spec §6 test 10) — RE-VERIFIED 2026-05-19: the ThisCode plugin-marketplace
// path is VERIFIED WORKING (valid .claude-plugin/marketplace.json + plugin.json;
// `claude plugin marketplace add` is a real Claude Code CLI command; user WSL
// run loaded 5 plugins). The earlier "unverified" caveat was over-cautious and
// factually wrong → it must NOT be reintroduced. The honest ThisCodex/Codex-side
// "verified broken" note must be retained (different harness, 손석희-verified).
test('A8: quickstart still has a runnable command block (clone/wizard is a valid entry)', () => {
  const blocks = readme.split('```');
  let firstCmds = '';
  for (let i = 1; i < blocks.length; i += 2) {
    if (/git clone|claude-discode-init|thiscode:init|claude plugin/i.test(blocks[i])) {
      firstCmds = blocks[i];
      break;
    }
  }
  assert.ok(firstCmds, 'README must have a quickstart command block');
});

test('A8: README does NOT falsely label the ThisCode plugin-marketplace path unverified', () => {
  assert.doesNotMatch(
    readme,
    /Plugin-marketplace path is unverified/i,
    'the false "unverified" caveat must not be reintroduced (re-verified working)',
  );
  assert.doesNotMatch(
    readme,
    /`claude plugin marketplace add`[\s\S]{0,80}not been verified/i,
    'must not claim `claude plugin marketplace add` is unverified for ThisCode',
  );
});

test('A8: README documents the ThisCode plugin-marketplace path as verified working', () => {
  assert.match(readme, /marketplace/i, 'README still references the marketplace path');
  // ThisCode-specific positive framing — must NOT be satisfied by the Codex
  // "verified broken" sentence (so this is a real RED→GREEN, not a false pass).
  assert.match(
    readme,
    /(plugin-marketplace|marketplace add)[\s\S]{0,400}(verified working|정상 작동 확인|works end-to-end|a supported install path)/i,
    'the ThisCode plugin-marketplace path must be framed verified working (A8 re-verified)',
  );
});

test('A8: README retains the honest Codex-side (ThisCodex) verified-broken note', () => {
  assert.match(
    readme,
    /Codex[\s\S]{0,160}(broken|verified broken)/i,
    'the ThisCodex/Codex plugin path is genuinely broken (손석희) — keep that note',
  );
  assert.match(readme, /ThisCodex/i, 'must point to ThisCodex for the Codex-side detail');
});
