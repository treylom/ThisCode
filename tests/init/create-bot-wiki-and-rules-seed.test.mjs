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
import { readFileSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

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

// Follow-up order (same commit): the wiki path answer is FREE TEXT (like
// ThisCodex's wiki_path, which ThisCodex protects with a `shQuote` helper —
// see ThisCodex tests/init/materialize.test.mjs "embedded single quote
// (exercises shQuote escaping itself)"). ThisCode has no equivalent JS
// materializer for bots (create-bot is pure SKILL.md), so the same "land as
// a value, never as code" contract has to be authored as a quoted-heredoc
// capture + printf '%q' / PowerShell single-quote-escape re-emission
// instead of a shQuote() call. These lock that the naive, re-interpretable
// pattern does not silently creep back in.
test('B4 (shell-safety parity with ThisCodex shQuote): the wiki path answer is captured via a quoted heredoc, not spliced into a double-quoted assignment', () => {
  const text = readSkill();
  assert.match(
    text,
    /WIKI_PATH=\$\(cat <<'THISCODE_WIKI_PATH_EOF'/,
    'the answer must be captured through a quoted heredoc (no shell re-interpretation of $()/backticks/quotes inside the answer)',
  );
  assert.doesNotMatch(
    text,
    /WIKI_PATH="<사용자 입력/,
    'the old double-quoted splice-in-place assignment must not reappear — that pattern lets shell metacharacters in the answer break out of the intended string',
  );
});

test('B4 (shell-safety parity): the printed launch export lines re-quote WIKI_PATH instead of naively double-quoting it', () => {
  const text = readSkill();
  assert.match(
    text,
    /printf '  export THISCODE_WIKI_PATH=%q\\n' "\$WIKI_PATH"/,
    'bash export lines must use printf %q (bash-safe re-quoting) so a copy-pasted value with quotes/$()/backticks still lands as one literal value',
  );
  assert.doesNotMatch(
    text,
    /echo "  export THISCODE_WIKI_PATH=\\"\$WIKI_PATH\\""/,
    'the old naive double-quoted echo of THISCODE_WIKI_PATH must not reappear',
  );
  assert.match(
    text,
    /sed "s\/'\/''\/g"/,
    'the PowerShell line must escape embedded single quotes by doubling them (PowerShell single-quoted strings are the only fully literal form there)',
  );
});

// Follow-up order (255941b 보완, ③): 글재경's review found that the quoted-heredoc
// capture above has its own hole — if the free-text answer contains a line that
// exactly equals the heredoc delimiter (THISCODE_WIKI_PATH_EOF), the heredoc
// terminates early right there and the captured value is silently truncated
// (on some shells the orphaned trailing text can even run as commands — see
// the CI-hotfix note on the repro test below for why that specific escalation
// is NOT what's asserted here). The fix is a pre-check, evaluated by the agent
// against its own copy of the raw answer text (never through a second shell
// command — doing the check in shell would just recreate the same
// early-termination hole in the check itself). These lock (a) the
// vulnerability is real without the guard, (b) the documented guard condition
// (grep -qxF: whole-line match, not substring) actually neutralizes it with
// zero side effects, and (c) a benign answer is unaffected.
test('B4-③: reproduces the heredoc delimiter-collision defect when no guard is applied (proves the capture boundary breaks)', () => {
  // 2026-08-10 CI hotfix (카파시 root-cause, 루돌프 CI RED 실측): the original
  // repro asserted a `touch` side effect from the text left over after the
  // early heredoc close. That side effect is bash-VERSION-dependent —
  // confirmed empirically: local bash 3.2 (macOS default) runs it, CI bash
  // 5.x (ubuntu/windows runners) does not, even though the early close itself
  // happens identically on both — heredoc terminator matching (a line exactly
  // equal to the delimiter ends the body) is basic POSIX shell grammar, not a
  // version quirk. Assert the version-independent part instead: the captured
  // value is silently truncated at the embedded delimiter line. That
  // truncation IS the vulnerability the guard exists to close — code
  // execution on some shells is a downstream escalation of the same boundary
  // break, not a separate defect. (Empirically re-verified on this machine's
  // bash 3.2 after the rewrite: status 0, stdout exactly "/tmp/evil".)
  const collidingAnswer = '/tmp/evil\nTHISCODE_WIKI_PATH_EOF';
  const script = `WIKI_PATH=$(cat <<'THISCODE_WIKI_PATH_EOF'\n${collidingAnswer}\nTHISCODE_WIKI_PATH_EOF\n)\nprintf '%s' "$WIKI_PATH"`;
  const result = spawnSync('bash', ['-c', script], { encoding: 'utf8' });
  assert.equal(result.status, 0, 'the naive capture must not error out — it silently truncates, it does not fail loudly');
  assert.notEqual(
    result.stdout,
    collidingAnswer,
    'without a guard, a delimiter-colliding answer must be captured incomplete — the heredoc terminates at the first line matching the delimiter, silently dropping everything after it (the boundary break the guard exists to close, deterministic on every bash version)',
  );
  assert.equal(result.stdout, '/tmp/evil', 'the capture stops exactly at the embedded delimiter line, losing the rest of the answer');
});

test('B4-③: the documented guard (whole-line match against the delimiter) blocks the same colliding input with zero side effects', () => {
  const marker = join(tmpdir(), `gljk-guarded-${process.pid}`);
  const collidingAnswer = `/tmp/evil\nTHISCODE_WIKI_PATH_EOF\ntouch '${marker}'\necho unused <<'THISCODE_WIKI_PATH_EOF'`;
  // Mirrors the guard condition documented in SKILL.md: grep -qxF (whole-line,
  // fixed-string) against the delimiter, evaluated BEFORE any heredoc is built.
  const guardScript = `RAW_ANSWER=$(cat); if printf '%s\\n' "$RAW_ANSWER" | grep -qxF 'THISCODE_WIKI_PATH_EOF'; then echo TRIPPED; else echo PASSED; fi`;
  const result = spawnSync('bash', ['-c', guardScript], { input: collidingAnswer, encoding: 'utf8' });
  assert.equal(result.stdout.trim(), 'TRIPPED');
  assert.equal(existsSync(marker), false, 'the guard must prevent the heredoc from ever being built — no side effect');
});

test('B4-③: the same guard passes a benign answer through unaffected', () => {
  const benignAnswer = '/Users/x/my-real-vault';
  const guardScript = `RAW_ANSWER=$(cat); if printf '%s\\n' "$RAW_ANSWER" | grep -qxF 'THISCODE_WIKI_PATH_EOF'; then echo TRIPPED; else echo PASSED; fi`;
  const result = spawnSync('bash', ['-c', guardScript], { input: benignAnswer, encoding: 'utf8' });
  assert.equal(result.stdout.trim(), 'PASSED');
});

test('B4-③: SKILL.md documents the guard as a pre-check (before the heredoc), the whole-line criterion, and the non-blocking re-prompt', () => {
  const text = readSkill();
  const guardIdx = text.indexOf('구분자 충돌 가드');
  const heredocIdx = text.indexOf("WIKI_PATH=$(cat <<'THISCODE_WIKI_PATH_EOF'");
  assert.ok(guardIdx > -1 && heredocIdx > -1, 'both the guard prose and the heredoc capture must exist');
  assert.ok(guardIdx < heredocIdx, 'the guard must be documented BEFORE the heredoc it protects, not after');
  assert.match(text, /grep -qxF/, 'the whole-line, fixed-string match criterion must be named explicitly (not substring matching)');
  // the re-prompt sentence wraps across a markdown line break in the source ("예약\n문자열이"),
  // so match on whitespace-normalized text rather than a literal contiguous phrase.
  assert.match(
    text.replace(/\s+/g, ' '),
    /경로에 예약 문자열이 포함되어 있습니다 — 다시 입력해 주세요/,
    'the failure path must be a re-prompt, not a hard refusal (no-block invariant)',
  );
  assert.match(text, /셸을 거치지 않고/, 'the guard must be evaluated in agent context, not via a second shell command (which would recreate the same hole)');
});
