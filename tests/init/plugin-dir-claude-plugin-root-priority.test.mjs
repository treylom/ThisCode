// Fix F (2026-08-10, 루돌프 4차 실측): the shared PLUGIN_DIR ordered-probe (used by
// commands/test.md, skills/install-hooks/SKILL.md, skills/create-bot/SKILL.md,
// skills/slack-configure/SKILL.md) picks the FIRST candidate that has the marker
// file/dir — "first match wins", not "freshest wins". When candidate #1 (the
// marketplace clone) is stale, it still wins over candidate #5 (the version
// cache, which is what `/plugin install` actually keeps fresh) — and because the
// marker check only proves "a real thiscode install", not "the CURRENT one", the
// probe silently resolves to the stale copy. The observed real-world consequence:
// a stale marketplace clone missing rules-seed.md/templates/rules-seed.md wins,
// and create-bot silently ships a bot with no rules-seed.md — no error, no
// warning, nothing on screen (a shipped-feature (B3/Fix C) failing in total
// silence).
//
// The fix: try `${CLAUDE_PLUGIN_ROOT}` first. That token is a literal placeholder
// in the markdown text itself — Claude Code substitutes it with the plugin's real
// install path when it loads the skill/command content (not a shell env var the
// Bash tool resolves) — so when it resolves, the ordering competition among
// candidates never happens at all. These tests simulate "already resolved" by
// setting CLAUDE_PLUGIN_ROOT in the child process's env before running the
// extracted bash block (spawnSync env is exactly how a real resolved substitution
// would appear to the script), and prove it wins over a stale candidate #1 planted
// alongside it. A second pass (CLAUDE_PLUGIN_ROOT unset) re-proves the existing
// fallback probe is untouched — the no-regression contract team-lead required.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

function read(rel) {
  return readFileSync(rel, 'utf8').replace(/\r\n/g, '\n');
}

// Extract the PLUGIN_DIR-resolution sub-block between two literal anchors
// (inclusive of the start anchor's line, exclusive of the end anchor).
function extractBetween(text, startAnchor, endAnchor) {
  const start = text.indexOf(startAnchor);
  assert.ok(start > -1, `start anchor not found: ${startAnchor}`);
  const end = text.indexOf(endAnchor, start);
  assert.ok(end > -1, `end anchor not found: ${endAnchor}`);
  return text.slice(start, end);
}

const TARGETS = [
  {
    file: 'commands/test.md',
    marker: 'scripts/feature-test.mjs',
    isDir: false,
    startAnchor: 'PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"',
    endAnchor: '# node 우선',
  },
  {
    file: 'skills/install-hooks/SKILL.md',
    marker: 'hooks/bot-session-init.sh',
    isDir: false,
    startAnchor: 'PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"',
    endAnchor: '```\n\n### Step 2.',
  },
  {
    file: 'skills/create-bot/SKILL.md',
    marker: 'templates',
    isDir: true,
    startAnchor: 'if [ -z "${PLUGIN_DIR:-}" ] || [ ! -d "$PLUGIN_DIR/templates" ]; then\n  PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"',
    endAnchor: 'TEMPLATE="$PLUGIN_DIR/templates/soul-',
  },
  {
    file: 'skills/slack-configure/SKILL.md',
    marker: 'templates',
    isDir: true,
    startAnchor: 'if [ -z "${PLUGIN_DIR:-}" ] || [ ! -d "$PLUGIN_DIR/templates" ]; then\n  PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"',
    endAnchor: 'TEMPLATE="$PLUGIN_DIR/templates/soul-',
  },
];

function plant(dir, marker, isDir) {
  if (isDir) {
    mkdirSync(join(dir, marker), { recursive: true });
  } else {
    mkdirSync(join(dir, ...marker.split('/').slice(0, -1)), { recursive: true });
    writeFileSync(join(dir, marker), '// marker\n');
  }
}

function runBlock(block, env) {
  const dir = mkdtempSync(join(tmpdir(), 'cpr-'));
  const script = join(dir, 'run.sh');
  writeFileSync(script, `${block}\necho "RESOLVED=$PLUGIN_DIR"\n`);
  const r = spawnSync('bash', [script], { env: { ...process.env, ...env }, encoding: 'utf8' });
  rmSync(dir, { recursive: true, force: true });
  const m = (r.stdout || '').match(/RESOLVED=(.*)/);
  return { code: r.status, resolved: m ? m[1].trim() : '', out: (r.stdout || '') + (r.stderr || '') };
}

const posix = (p) => p.replace(/\\/g, '/');

for (const t of TARGETS) {
  test(`Fix F (${t.file}): CLAUDE_PLUGIN_ROOT wins over a stale candidate #1 (the exact rules-seed silent-loss shape)`, () => {
    const text = read(t.file);
    const block = extractBetween(text, t.startAnchor, t.endAnchor);
    assert.match(block, /PLUGIN_DIR="\$\{CLAUDE_PLUGIN_ROOT\}"/, 'block must attempt CLAUDE_PLUGIN_ROOT first');

    const home = mkdtempSync(join(tmpdir(), 'cpr-home-'));
    const staleCand1 = join(home, '.claude/plugins/marketplaces/thiscode-marketplace');
    mkdirSync(staleCand1, { recursive: true });
    plant(staleCand1, t.marker, t.isDir); // stale candidate #1 — WOULD win under the old first-match probe

    const freshRoot = mkdtempSync(join(tmpdir(), 'cpr-fresh-'));
    plant(freshRoot, t.marker, t.isDir); // this is what a resolved CLAUDE_PLUGIN_ROOT would point at

    const r = runBlock(block, { HOME: home, CLAUDE_PLUGIN_ROOT: freshRoot, PLUGIN_DIR: '' });
    assert.equal(r.code, 0, `should succeed, got: ${r.out}`);
    assert.ok(
      posix(r.resolved) === posix(freshRoot),
      `must resolve to CLAUDE_PLUGIN_ROOT (${freshRoot}), not the stale candidate #1 (${staleCand1}); got: ${r.resolved}`,
    );
    rmSync(home, { recursive: true, force: true });
    rmSync(freshRoot, { recursive: true, force: true });
  });

  test(`Fix F (${t.file}): CLAUDE_PLUGIN_ROOT unset/empty falls back to the existing candidate probe (no regression)`, () => {
    const text = read(t.file);
    const block = extractBetween(text, t.startAnchor, t.endAnchor);

    const home = mkdtempSync(join(tmpdir(), 'cpr-home-'));
    const cand1 = join(home, '.claude/plugins/marketplaces/thiscode-marketplace');
    mkdirSync(cand1, { recursive: true });
    plant(cand1, t.marker, t.isDir);

    const r = runBlock(block, { HOME: home, CLAUDE_PLUGIN_ROOT: '', PLUGIN_DIR: '' });
    assert.equal(r.code, 0, `should succeed, got: ${r.out}`);
    assert.ok(
      posix(r.resolved).endsWith('/.claude/plugins/marketplaces/thiscode-marketplace'),
      `unset CLAUDE_PLUGIN_ROOT must fall back to the existing ordered probe; got: ${r.resolved}`,
    );
    rmSync(home, { recursive: true, force: true });
  });
}
