// Hotfix B (2026-08-10, 루돌프 실측 1536053876): /thiscode:test called
// `node scripts/feature-test.mjs $ARGUMENTS` with a bare cwd-relative path and
// no PLUGIN_DIR detection at all — the only invoker in the repo missing the
// ordered-probe pattern every other cwd-dependent invocation already uses
// (install-hooks.md, create-bot.md, slack-configure.md, self-update.md). When
// the agent's cwd happened to be a stale manual clone (~/.claude/plugins/thiscode,
// missing the discord-gate feature), that stale copy's own
// scripts/feature-test.mjs got picked and ran (7/7, "회귀 아님" false negative)
// instead of the installed 1.2.5 copy (8/8). These tests (a) prove the doc no
// longer contains the bare unguarded invocation, (b) behaviorally prove the
// extracted probe+invoke block resolves to the fresher marketplace install
// even when a stale manual clone also exists and even when cwd sits inside
// that stale clone (the exact shape of Rudolf's repro), and (c) prove a
// single-install (no marketplace) layout still works.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const md = readFileSync(
  fileURLToPath(new URL('../../commands/test.md', import.meta.url)),
  'utf8',
);

test('doc no longer bare-invokes feature-test.mjs cwd-relative with no PLUGIN_DIR (regression lock)', () => {
  assert.doesNotMatch(
    md,
    /^\s*node scripts\/feature-test\.mjs \$ARGUMENTS/m,
    'the old cwd-trusting invocation must not reappear — it silently picks up whatever "scripts/feature-test.mjs" happens to resolve from cwd',
  );
  assert.match(
    md,
    /node "\$PLUGIN_DIR\/scripts\/feature-test\.mjs" \$ARGUMENTS/,
    'the fixed invocation must run the PLUGIN_DIR-resolved copy, not a bare relative path',
  );
  assert.match(md, /for _cand in/, 'must reuse the same ordered-probe shape as install-hooks.md/create-bot.md');
});

// Extract the first ```bash block containing the ordered probe + the actual invocation.
function extractBlock() {
  const blocks = md.split('```');
  for (let i = 1; i < blocks.length; i += 2) {
    const body = blocks[i].replace(/^bash\n/, '');
    if (/for _cand in/.test(body) && /feature-test\.mjs/.test(body)) return body;
  }
  return '';
}
const BLOCK = extractBlock();

test('probe+invoke block was extractable from commands/test.md', () => {
  assert.ok(BLOCK && /for _cand in/.test(BLOCK) && /PLUGIN_DIR=/.test(BLOCK), 'must find the ordered-probe + invoke bash block');
});

function plantFeatureTest(root, rel, markerOutput) {
  const dir = join(root, rel, 'scripts');
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'feature-test.mjs'), `console.log(${JSON.stringify(markerOutput)});\n`);
}

function runBlock({ home, cwd }) {
  const dir = mkdtempSync(join(tmpdir(), 'tcpd-'));
  const script = join(dir, 'run.sh');
  writeFileSync(script, BLOCK);
  const r = spawnSync('bash', [script], {
    cwd,
    env: { ...process.env, HOME: home },
    encoding: 'utf8',
  });
  rmSync(dir, { recursive: true, force: true });
  return { code: r.status, out: (r.stdout || '') + (r.stderr || '') };
}

test('E2E (Rudolf repro shape): stale manual clone + fresh marketplace install both present, cwd sits inside the stale clone — the FRESH copy must run, not the stale one', () => {
  const home = mkdtempSync(join(tmpdir(), 'tcpd-home-'));
  const staleDir = join(home, '.claude/plugins/thiscode');
  plantFeatureTest(home, '.claude/plugins/thiscode', 'STALE-7-no-discord-gate');
  plantFeatureTest(home, '.claude/plugins/marketplaces/thiscode-marketplace', 'FRESH-8-with-discord-gate');
  const r = runBlock({ home, cwd: staleDir }); // cwd = literally inside the stale clone, per Rudolf's repro
  assert.equal(r.code, 0, `should succeed, got: ${r.out}`);
  assert.match(r.out, /FRESH-8-with-discord-gate/, `must run the fresher marketplace install; got: ${r.out}`);
  assert.doesNotMatch(r.out, /STALE-7-no-discord-gate/, `must NOT run the stale manual clone even though cwd is inside it; got: ${r.out}`);
  rmSync(home, { recursive: true, force: true });
});

test('single-install layout (no marketplace dir) still resolves and runs the only candidate present', () => {
  const home = mkdtempSync(join(tmpdir(), 'tcpd-home-'));
  plantFeatureTest(home, '.claude/plugins/thiscode', 'ONLY-INSTALL');
  const r = runBlock({ home, cwd: home });
  assert.equal(r.code, 0, `should succeed, got: ${r.out}`);
  assert.match(r.out, /ONLY-INSTALL/, `must still find and run the sole install; got: ${r.out}`);
  rmSync(home, { recursive: true, force: true });
});

test('no candidate present anywhere → clean exit 1 with the not-found message, not a crash', () => {
  const home = mkdtempSync(join(tmpdir(), 'tcpd-home-'));
  mkdirSync(join(home, '.claude'), { recursive: true }); // empty, nothing planted
  const r = runBlock({ home, cwd: home });
  assert.equal(r.code, 1, 'must exit 1 when nothing is found');
  assert.match(r.out, /못 찾음|not found/i, 'must print the not-found message');
  assert.doesNotMatch(r.out, /No such file|syntax error|unbound variable/i, 'unmatched glob candidate must not crash the probe');
  rmSync(home, { recursive: true, force: true });
});
