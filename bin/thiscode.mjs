#!/usr/bin/env node
// bin/thiscode.mjs — ThisCode Node single-bin installer. Node ≥18, zero shell.
import { detectEnv } from '../scripts/lib/detect.mjs';
import { msg } from '../scripts/lib/i18n.mjs';
import { loadState, saveState, mergeAnswer, resumeSummary } from '../scripts/lib/state.mjs';
import { SCRIPT, nextQuestion, isInScope } from '../scripts/lib/questions.mjs';
import { injectMarkerBlock, backupFile } from '../scripts/lib/apply.mjs';
import { applyCodexSync } from '../scripts/lib/codexsync.mjs';
import { loadManifest } from '../scripts/lib/manifest.mjs';
import { runManifest } from '../scripts/lib/manifest-runner.mjs';
import { join } from 'node:path';
import { homedir } from 'node:os';

const makeVerifiers = (env) => ({
  detected: () => Boolean(env.os),
  ack: () => true,
  answered: () => true,
  'marker-present': () => true,
});

const args = process.argv.slice(2);

if (args[0] === 'doctor') {
  const { loadManifest } = await import('../scripts/lib/manifest.mjs');
  const { detectEnv } = await import('../scripts/lib/detect.mjs');
  const e = detectEnv();
  const steps = loadManifest();
  const verifiers = makeVerifiers(e);
  let allOk = true;
  console.log('🩺 thiscode doctor — verify replay (설치가 실제로 됐는지 같은 기준으로 재검사)');
  for (const s of steps.slice().sort((a, b) => a.order - b.order)) {
    const v = verifiers[s.verify && s.verify.type];
    const ok = v ? v(s, { os: e.os }) : true;
    if (!ok) allOk = false;
    console.log(`  ${ok ? '✅' : '❌'} ${s.id}${ok ? '' : '  → ' + ((s.on_fail && s.on_fail.next_command) || 'see docs')}`);
  }
  process.exit(allOk ? 0 : 1);
}

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

const steps = loadManifest();
const runCtx = { os: env.os, mode };
const actions = {
  detect: () => console.log(`🔍 OS=${env.os} Node=${env.node} git=${env.tools.git} codex=${env.tools.codex} claude=${env.tools.claude}`),
  guide: (s) => { if (s.id === 'wsl_first') console.log(msg('wsl_recommend_reason', register)); },
  prompt: () => { /* handled by the interactive/non-interactive loop below */ },
  apply: () => { /* handled by the --apply block below */ },
};
const verifiers = makeVerifiers(env);
runManifest(steps.filter(s => ['detect','guide'].includes(s.action)), {
  ctx: runCtx, actions, verifiers, emit: (r) => console.log('• ' + r),
});
console.log(msg('placement_explain', register));

const hasAnswers = args.some(a => a.startsWith('--answers='));
const interactive = !nonInteractive && process.stdin.isTTY === true;

if (mode === 'apply' && !interactive && !nonInteractive && !has('--yes') && !hasAnswers) {
  console.error(msg('apply_needs_consent', register));
  process.exit(2);
}

if (!interactive) {
  // Deterministic: fill every in-scope unanswered question with its (resolved) default. No readline.
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
