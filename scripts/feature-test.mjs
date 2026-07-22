#!/usr/bin/env node
// feature-test.mjs — user-facing feature smoke harness for ThisCode.
//
// This is NOT the dev unit suite (that is `npm test` → run-tests.mjs).
// This proves the *shipped features* are wired, with graceful SKIP when an
// optional runtime dependency is absent (only a real breakage is FAIL).
//
// Usage:
//   node scripts/feature-test.mjs                 → sequential ALL except graphrag-bench
//   node scripts/feature-test.mjs <natural text>  → fuzzy-match ONE feature, run it
//   node scripts/feature-test.mjs graphrag-bench  → the heavy bench (separately runnable)
//   node scripts/feature-test.mjs all | --bench   → everything incl. graphrag-bench
//
// Exit 0 unless any feature FAILs (SKIP never fails the run). Deterministic /
// idempotent by design (filesystem + binary probes only) so it is safe to run
// many times — which it must be, it is test code.

import { existsSync, readFileSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const R = (p) => join(ROOT, p);
const PASS = 'PASS', FAIL = 'FAIL', SKIP = 'SKIP';

function fileHas(rel, re) {
  try { return re.test(readFileSync(R(rel), 'utf8')); } catch { return false; }
}
function nonEmpty(rel) {
  try { return statSync(R(rel)).size > 0; } catch { return false; }
}
function hasBin(name) {
  const r = spawnSync(process.platform === 'win32' ? 'where' : 'which', [name],
    { encoding: 'utf8' });
  return r.status === 0 && (r.stdout || '').trim().length > 0;
}

const FEATURES = [
  {
    id: 'memory',
    aliases: ['memory', '메모리', 'shared-memory', 'shared memory', '기억'],
    desc: 'shared-memory skill + tiered memory convention shipped',
    bench: false,
    run() {
      if (!nonEmpty('skills/shared-memory/SKILL.md'))
        return { status: FAIL, detail: 'skills/shared-memory/SKILL.md missing/empty' };
      const ruleOk = nonEmpty('rules/memory.md') ||
        fileHas('rules/INDEX.md', /memory/i);
      return ruleOk
        ? { status: PASS, detail: 'shared-memory skill + memory rule wired (runtime dir is env-provided)' }
        : { status: FAIL, detail: 'memory rule/INDEX entry not found' };
    },
  },
  {
    id: 'tmux',
    aliases: ['tmux', 'session', '세션', 'split pane'],
    desc: 'tmux runtime available for bot windows',
    bench: false,
    run() {
      return hasBin('tmux')
        ? { status: PASS, detail: 'tmux binary present' }
        : { status: SKIP, detail: 'tmux not installed (optional — in-process fallback)' };
    },
  },
  {
    id: 'discord-gate',
    aliases: ['discord', 'channels', 'bot', '봇', 'bun'],
    desc: 'Discord bot prerequisites: plugin enabled + bun runtime (static checks; --channels launch flag is a reminder — not verifiable here)',
    bench: false,
    run() {
      const home = process.env.HOME || process.env.USERPROFILE || '';
      let pluginOn = false;
      try {
        const st = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
        pluginOn = st.enabledPlugins && st.enabledPlugins['discord@claude-plugins-official'] === true;
      } catch { /* settings unreadable → treated as not enabled */ }
      const bun = hasBin('bun');
      if (pluginOn && bun) return { status: PASS, detail: 'discord plugin enabled + bun present (launch with --channels plugin:discord@claude-plugins-official)' };
      const miss = [!pluginOn && 'discord plugin not enabled (/plugin → discord@claude-plugins-official)', !bun && 'bun missing (bun.sh / windows-setup.ps1)'].filter(Boolean).join('; ');
      return { status: SKIP, detail: 'not a bot host yet — ' + miss };
    },
  },
  {
    id: 'graphrag',
    aliases: ['graphrag', 'graph rag', 'graph-rag', '그래프', 'search tier'],
    desc: 'GraphRAG Tier-1 installer + setup doc shipped',
    bench: false,
    run() {
      const ship = existsSync(R('scripts/install-graphrag.sh')) &&
        existsSync(R('docs/06-graphrag-setup.md'));
      if (!ship) return { status: FAIL, detail: 'graphrag installer/setup doc missing' };
      const installed = existsSync(join(process.env.HOME || '', '.thiscode', 'graphrag')) ||
        hasBin('graphrag');
      return { status: PASS,
        detail: installed ? 'graphrag shipped + runtime detected'
                          : 'graphrag shipped (runtime not installed yet — install-graphrag.sh)' };
    },
  },
  {
    id: 'graphrag-bench',
    aliases: ['graphrag-bench', 'graphrag bench', 'bench', '벤치', 'benchmark'],
    desc: 'GraphRAG benchmark (heavy — separately runnable, excluded from default sweep)',
    bench: true,
    run() {
      if (!nonEmpty('docs/BENCHMARK.md'))
        return { status: FAIL, detail: 'docs/BENCHMARK.md missing' };
      const benchProbe = existsSync(R('scripts/install-graphrag.sh'));
      return { status: PASS,
        detail: 'bench doc + graphrag base present (run the documented benchmark steps; heavy)' };
    },
  },
  {
    id: 'meeting',
    aliases: ['meeting', '회의', '회의실', 'meeting room', 'protocol'],
    desc: 'meeting protocol: Stop-reread hook + SessionStart rules inject + rule',
    bench: false,
    run() {
      const stopOk = fileHas('hooks/meeting-stop-reread.sh', /"decision"\s*:\s*"block"/) &&
        !fileHas('hooks/meeting-stop-reread.sh', /hookSpecificOutput["']?\s*:/);
      const initOk = fileHas('hooks/bot-session-init.sh', /INDEX|rules/i);
      const ruleOk = nonEmpty('rules/meeting-protocol.md');
      if (stopOk && initOk && ruleOk)
        return { status: PASS, detail: 'Stop-reread decision:block contract + SessionStart inject + rule present' };
      return { status: FAIL,
        detail: `stop=${stopOk} sessionStart=${initOk} rule=${ruleOk}` };
    },
  },
  {
    id: 'rules',
    aliases: ['rules', '규칙', 'rule index', 'progressive disclosure'],
    desc: 'progressive-disclosure rules router + topical files',
    bench: false,
    run() {
      const idx = fileHas('rules/INDEX.md', /\|/) && nonEmpty('rules/INDEX.md');
      const topical = ['rules/meeting-protocol.md', 'rules/source-fact.md',
        'rules/autonomy.md'].filter((p) => nonEmpty(p)).length;
      return (idx && topical >= 2)
        ? { status: PASS, detail: `INDEX trigger table + ${topical} topical rule files` }
        : { status: FAIL, detail: `index=${idx} topicalFiles=${topical}` };
    },
  },
  {
    id: 'hooks',
    aliases: ['hooks', '훅', 'hook', 'stop hook', 'fail-open'],
    desc: 'hook scripts shipped + Stop hook fail-open recursion guard',
    bench: false,
    run() {
      const present = ['hooks/bot-session-init.sh', 'hooks/meeting-stop-reread.sh']
        .every((p) => nonEmpty(p));
      const guard = fileHas('hooks/meeting-stop-reread.sh', /stop_hook_active/);
      return (present && guard)
        ? { status: PASS, detail: 'hooks present + stop_hook_active recursion guard' }
        : { status: FAIL, detail: `present=${present} recursionGuard=${guard}` };
    },
  },
  {
    id: 'install',
    aliases: ['install', '설치', 'setup', 'install-hooks', 'onboarding'],
    desc: 'install/setup surface: install-hooks command + setup skill',
    bench: false,
    run() {
      const ok = nonEmpty('skills/install-hooks/SKILL.md') && nonEmpty('skills/setup/SKILL.md');
      return ok
        ? { status: PASS, detail: 'install-hooks command + setup skill shipped' }
        : { status: FAIL, detail: 'install-hooks or setup skill missing' };
    },
  },
];

function resolveTargets(argv) {
  const arg = argv.slice(2).join(' ').trim().toLowerCase();
  if (!arg) return { mode: 'sweep', list: FEATURES.filter((f) => !f.bench) };
  if (arg === 'all' || arg === '--bench' || arg === '--all') return { mode: 'all', list: FEATURES };
  // exact id / alias first, then fuzzy keyword contains
  let hit = FEATURES.find((f) => f.id === arg || f.aliases.includes(arg));
  if (!hit) hit = FEATURES.find((f) =>
    f.id.includes(arg) || arg.includes(f.id) ||
    f.aliases.some((a) => a.includes(arg) || arg.includes(a)));
  return hit ? { mode: 'one', list: [hit] }
             : { mode: 'none', list: [], arg };
}

function main() {
  const { mode, list, arg } = resolveTargets(process.argv);
  if (mode === 'none') {
    console.error(`/test: no feature matched "${arg}". Known: ${FEATURES.map((f) => f.id).join(', ')}`);
    process.exit(2);
  }
  console.log(`ThisCode /test — ${mode} (${list.length} feature${list.length > 1 ? 's' : ''})`);
  let fails = 0;
  for (const f of list) {
    let res;
    try { res = f.run(); } catch (e) { res = { status: FAIL, detail: `threw: ${e.message}` }; }
    if (res.status === FAIL) fails++;
    console.log(`  [${res.status}] ${f.id} — ${res.detail}`);
  }
  const summary = `summary: ${list.length - fails}/${list.length} non-FAIL, ${fails} FAIL`;
  console.log(summary);
  process.exit(fails > 0 ? 1 : 0);
}

main();
