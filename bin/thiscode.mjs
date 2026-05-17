#!/usr/bin/env node
// bin/thiscode.mjs — ThisCode Node single-bin installer. Node ≥18, zero shell.
import { detectEnv } from '../scripts/lib/detect.mjs';
import { recommendPhases } from '../scripts/lib/recommend.mjs';
import { msg } from '../scripts/lib/i18n.mjs';
import { loadState, saveState, mergeAnswer, resumeSummary } from '../scripts/lib/state.mjs';
import { SCRIPT, nextQuestion, isInScope } from '../scripts/lib/questions.mjs';
import { injectMarkerBlock, backupFile } from '../scripts/lib/apply.mjs';
import { join } from 'node:path';

const args = process.argv.slice(2);
const has = f => args.includes(f);
const toneArg = (args.find(a => a.startsWith('--tone=')) || '').split('=')[1];
const mode = has('--apply') ? 'apply' : 'check';
const nonInteractive = has('--non-interactive');
const repoRoot = process.cwd();

const env = detectEnv();
let state = loadState(repoRoot);
const register = toneArg || state.answers.tone || 'plain';

if (has('--resume')) console.log(resumeSummary(state));

console.log(`🔍 OS=${env.os} Node=${env.node} git=${env.tools.git} codex=${env.tools.codex} claude=${env.tools.claude}`);
console.log(msg('placement_explain', register));
const rec = recommendPhases({
  note_count: 0, python: env.tools.python, obsidian_cli: false,
});
console.log(`📊 현재=${rec.current.join(',')} 권장=${rec.recommended.join(',')} 나중=${rec.later.join(',')}`);

// Non-interactive: apply defaults for every in-scope, unanswered question (nothing skipped)
if (nonInteractive) {
  let ctx = { os: env.os, answers: state.answers };
  let q;
  while ((q = nextQuestion(ctx, state.completed_steps))) {
    state = mergeAnswer(state, q.id, state.answers[q.id] ?? q.default);
    ctx = { os: env.os, answers: state.answers };
  }
} else {
  const rl = (await import('node:readline/promises')).createInterface({ input: process.stdin, output: process.stdout });
  let ctx = { os: env.os, answers: state.answers };
  let q;
  while ((q = nextQuestion(ctx, state.completed_steps))) {
    const a = (await rl.question(`${q.ask} [${q.choices.join('/')}] (기본 ${q.default}): `)).trim() || q.default;
    state = mergeAnswer(state, q.id, a);
    ctx = { os: env.os, answers: state.answers };
  }
  rl.close();
}

if (mode === 'check') {
  console.log(msg('check_only_notice', register));
  process.exit(0);
}

// --apply: backup + inject + persist state
console.log(msg('apply_backup_notice', register));
const target = join(repoRoot, 'CLAUDE.md');
backupFile(target);
injectMarkerBlock(target,
  '## ThisCode rules-system pointer\nSee `rules/INDEX.md` — situational rule router (progressive disclosure).');
saveState(repoRoot, state);
console.log('✅ apply 완료. state: .thiscode-init-state.json');
process.exit(0);
