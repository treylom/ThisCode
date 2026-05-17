#!/usr/bin/env node
// bin/thiscode.mjs — ThisCode Node single-bin installer. Node ≥18, zero shell.
import { detectEnv } from '../scripts/lib/detect.mjs';
import { recommendPhases } from '../scripts/lib/recommend.mjs';
import { msg } from '../scripts/lib/i18n.mjs';
import { loadState, saveState, mergeAnswer, resumeSummary } from '../scripts/lib/state.mjs';
import { SCRIPT, nextQuestion, isInScope } from '../scripts/lib/questions.mjs';
import { injectMarkerBlock, backupFile } from '../scripts/lib/apply.mjs';
import { applyCodexSync } from '../scripts/lib/codexsync.mjs';
import { join } from 'node:path';
import { homedir } from 'node:os';

const args = process.argv.slice(2);
const has = f => args.includes(f);
const toneArg = (args.find(a => a.startsWith('--tone=')) || '').split('=')[1];
const mode = has('--apply') ? 'apply' : 'check';
const nonInteractive = has('--non-interactive');
const repoRoot = process.cwd();

const env = detectEnv();
let state = loadState(repoRoot);
const register = toneArg || state.answers.tone || 'plain';

// Resolve the 'auto' harness sentinel from detected tools (DA-review fix 2026-05-17):
// questions.mjs harness default 'auto' is NOT in choices[claude,codex,both] — it must
// be resolved by tool detection, else codexsync gate + Q3c–f Codex subtree stay dead
// in non-interactive (and the displayed interactive default would be the invalid 'auto').
const detectedHarness = env.tools.codex && env.tools.claude ? 'both'
  : env.tools.codex ? 'codex' : 'claude';
const effDefault = q => (q.id === 'harness' && q.default === 'auto') ? detectedHarness : q.default;

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
    state = mergeAnswer(state, q.id, state.answers[q.id] ?? effDefault(q));
    ctx = { os: env.os, answers: state.answers };
  }
} else {
  const rl = (await import('node:readline/promises')).createInterface({ input: process.stdin, output: process.stdout });
  let ctx = { os: env.os, answers: state.answers };
  let q;
  while ((q = nextQuestion(ctx, state.completed_steps))) {
    const d = effDefault(q);
    const a = (await rl.question(`${q.ask} [${q.choices.join('/')}] (기본 ${d}): `)).trim() || d;
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
if (['codex','both'].includes(state.answers.harness) && state.answers.codex_skill_layer !== 'repo') {
  const dest = join(homedir(), '.agents', 'skills');
  const synced = applyCodexSync(join(repoRoot, 'skills'), dest);
  console.log(`🔁 Codex skill sync → ${dest} (${synced.join(', ')})`);
}
console.log('✅ apply 완료. state: .thiscode-init-state.json');
process.exit(0);
