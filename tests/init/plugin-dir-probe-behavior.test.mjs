// Codex review CONCERN 3: the PLUGIN_DIR detect tests were doc-lint only —
// add a BEHAVIORAL test that extracts the ordered-probe bash block from
// install-hooks.md and actually runs it against fixture HOME layouts, so
// glob-safety / ordering / not-found exit are exercised, not just asserted
// as substrings.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const md = readFileSync(
  fileURLToPath(new URL('../../commands/install-hooks.md', import.meta.url)),
  'utf8',
);

// Extract the first ```bash block that contains the ordered probe.
function extractProbe() {
  const blocks = md.split('```');
  for (let i = 1; i < blocks.length; i += 2) {
    const body = blocks[i].replace(/^bash\n/, '');
    if (/for _cand in/.test(body) && /PLUGIN_DIR=/.test(body)) return body;
  }
  return '';
}
const PROBE = extractProbe();

function runProbe(home) {
  const dir = mkdtempSync(join(tmpdir(), 'pdp-'));
  const script = join(dir, 'probe.sh');
  // Append a marker echo so we can read the resolved value on success.
  writeFileSync(script, `${PROBE}\necho "RESOLVED=$PLUGIN_DIR"\n`);
  const r = spawnSync('bash', [script], {
    env: { ...process.env, HOME: home },
    encoding: 'utf8',
  });
  rmSync(dir, { recursive: true, force: true });
  const m = (r.stdout || '').match(/RESOLVED=(.*)/);
  return { code: r.status, resolved: m ? m[1].trim() : '', out: (r.stdout || '') + (r.stderr || '') };
}

function plant(home, rel) {
  const p = join(home, rel, 'hooks');
  mkdirSync(p, { recursive: true });
  writeFileSync(join(p, 'bot-session-init.sh'), '#!/usr/bin/env bash\n');
}

test('probe block was extractable from install-hooks.md', () => {
  assert.ok(PROBE && /for _cand in/.test(PROBE), 'must find the ordered-probe bash block');
});

test('picks the only candidate that has hooks/bot-session-init.sh', () => {
  const home = mkdtempSync(join(tmpdir(), 'pdp-home-'));
  plant(home, '.claude/plugins/thiscode'); // manual-clone location only
  const r = runProbe(home);
  assert.equal(r.code, 0, `should succeed, got: ${r.out}`);
  assert.equal(r.resolved, join(home, '.claude/plugins/thiscode'));
  rmSync(home, { recursive: true, force: true });
});

test('ordering: marketplace dir wins over manual clone when both present', () => {
  const home = mkdtempSync(join(tmpdir(), 'pdp-home-'));
  plant(home, '.claude/plugins/marketplaces/thiscode-marketplace');
  plant(home, '.claude/plugins/thiscode');
  const r = runProbe(home);
  assert.equal(r.code, 0);
  assert.equal(
    r.resolved,
    join(home, '.claude/plugins/marketplaces/thiscode-marketplace'),
    'first candidate in the ordered list must win',
  );
  rmSync(home, { recursive: true, force: true });
});

test('no candidate + unmatched glob → clean exit 1, not a crash', () => {
  const home = mkdtempSync(join(tmpdir(), 'pdp-home-'));
  mkdirSync(join(home, '.claude'), { recursive: true }); // empty, nothing planted
  const r = runProbe(home);
  assert.equal(r.code, 1, 'must exit 1 when nothing is found');
  assert.match(r.out, /못 찾음|not found/i, 'must print the not-found message');
  assert.doesNotMatch(r.out, /No such file|syntax error|unbound variable/i,
    'unmatched glob must not crash the probe');
  rmSync(home, { recursive: true, force: true });
});
