// ⓑ J-2 permanent patch-layer (spec §10.1). scripts/patch-discord-bot-drop.sh
// idempotently re-applies the 3-guard to the EXTERNAL official discord plugin
// after a plugin update overwrites it. Safety: backup, exact-match-only,
// idempotent (marker), fail-open (always exit 0 so /self-update never bricks),
// warn-not-edit if upstream changed shape. RED before the script, GREEN after.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync, readFileSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT = fileURLToPath(
  new URL('../../scripts/patch-discord-bot-drop.sh', import.meta.url),
);

const VULN = `import { Client } from 'discord.js'
const client = new Client({})

client.on('messageCreate', msg => {
  if (msg.author.bot) return
  handleInbound(msg).catch(e => process.stderr.write(\`discord: \${e}\\n\`))
})

async function handleInbound(msg) { await gate(msg) }
`;

// spawnSync so stderr is captured on EVERY exit code (the script is fail-open
// = exit 0, but writes WARN/skip notices to stderr — execFileSync would drop
// stderr on success). A regression to exit≠0 surfaces as code!==0.
function run(target) {
  const r = spawnSync('bash', [SCRIPT], {
    env: { ...process.env, PATCH_TARGET: target },
    encoding: 'utf8',
  });
  return { code: r.status ?? 1, stdout: r.stdout ?? '', stderr: r.stderr ?? '' };
}

test('vulnerable server.ts → 3-guard applied, marker + .bak, exit 0', () => {
  const dir = mkdtempSync(join(tmpdir(), 'j2-'));
  const f = join(dir, 'server.ts');
  writeFileSync(f, VULN);

  const r = run(f);
  assert.equal(r.code, 0, 'must be fail-open exit 0');

  const out = readFileSync(f, 'utf8');
  assert.match(out, /thiscode-j2-guard/, 'idempotency marker inserted');
  assert.match(out, /msg\.author\.id === client\.user\?\.id/, 'self-loop guard');
  assert.match(out, /msg\.webhookId/, 'webhook guard');
  assert.match(out, /msg\.author\.bot && !msg\.guild/, 'bot-DM guard');
  assert.doesNotMatch(
    out,
    /^\s*if \(msg\.author\.bot\) return;?\s*$/m,
    'the blanket drop line must be gone',
  );
  assert.match(out, /handleInbound\(msg\)/, 'handler call preserved');
  assert.ok(
    readdirSync(dir).some((n) => n.includes('thiscode-j2.bak')),
    'a .bak backup was taken before editing',
  );
  rmSync(dir, { recursive: true, force: true });
});

test('already-patched (marker present) → idempotent no-op, no 2nd .bak, exit 0', () => {
  const dir = mkdtempSync(join(tmpdir(), 'j2-'));
  const f = join(dir, 'server.ts');
  writeFileSync(f, VULN);
  run(f); // first patch
  const afterFirst = readFileSync(f, 'utf8');
  const baksAfterFirst = readdirSync(dir).filter((n) => n.includes('.bak')).length;

  const r = run(f); // second run
  assert.equal(r.code, 0);
  assert.equal(readFileSync(f, 'utf8'), afterFirst, 'content unchanged on re-run');
  assert.equal(
    readdirSync(dir).filter((n) => n.includes('.bak')).length,
    baksAfterFirst,
    'no extra backup on idempotent re-run',
  );
  assert.match(r.stdout, /already patched|no-op/i);
  rmSync(dir, { recursive: true, force: true });
});

test('upstream shape changed (no vuln line, no marker) → warn, no edit, exit 0', () => {
  const dir = mkdtempSync(join(tmpdir(), 'j2-'));
  const f = join(dir, 'server.ts');
  const benign = "client.on('messageCreate', msg => { handleInbound(msg) })\n";
  writeFileSync(f, benign);

  const r = run(f);
  assert.equal(r.code, 0, 'fail-open');
  assert.equal(readFileSync(f, 'utf8'), benign, 'must NOT blindly edit unknown shape');
  assert.match(r.stderr + r.stdout, /WARN|manual review|not found/i);
  rmSync(dir, { recursive: true, force: true });
});

test('target missing → skip, exit 0 (never bricks /self-update)', () => {
  const dir = mkdtempSync(join(tmpdir(), 'j2-'));
  const r = run(join(dir, 'does-not-exist.ts'));
  assert.equal(r.code, 0);
  assert.match(r.stdout + r.stderr, /not found|skip/i);
  rmSync(dir, { recursive: true, force: true });
});

// Codex review AREA 3: fail-open must hold even with PATCH_TARGET unset AND
// HOME unset under `set -u` (no unbound-variable abort).
test('PATCH_TARGET unset + HOME unset → fail-open exit 0, no set -u crash', () => {
  const r = spawnSync('bash', [SCRIPT], {
    env: { PATH: process.env.PATH }, // no PATCH_TARGET, no HOME
    encoding: 'utf8',
  });
  assert.equal(r.status, 0, 'must stay fail-open (exit 0) with HOME unset');
  assert.doesNotMatch(
    (r.stderr ?? '') + (r.stdout ?? ''),
    /unbound variable|HOME: parameter|set -u/i,
    'must not abort on unbound HOME',
  );
  assert.match((r.stdout ?? '') + (r.stderr ?? ''), /not found|skip/i);
});
