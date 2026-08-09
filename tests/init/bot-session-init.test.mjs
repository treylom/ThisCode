// Regression locks for the WSL repo-handoff debug log (2026-05-18) findings
// B/C/D against hooks/bot-session-init.sh. RED before the fix, GREEN after.
//
//   B — WD→memory encoding must match Claude Code's real ~/.claude/projects
//       encoding (spaces / non-ASCII), not only `/` and `_`.
//   C — a bare `discord` state dir (no `discord-<bot>` suffix) must NOT
//       mis-inject a `discord-discord/soul.md: MISSING` placeholder.
//   D — a workspace-local `shared-memory/SHARED-INDEX.md` must be detected
//       even when CLAUDE_DISCODE_VAULT / ~/.thiscode are absent.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync, copyFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HOOK = fileURLToPath(new URL('../../hooks/bot-session-init.sh', import.meta.url));

// Run the hook with an isolated HOME so it never reads the real ~/.claude.
// Returns { stdout } (the hook always exits 0; empty stdout = silent skip).
function runHook({ cwd, stateDir, home }) {
  const env = { PATH: process.env.PATH };
  if (stateDir) env.DISCORD_STATE_DIR = stateDir;
  if (home) env.HOME = home;
  const stdout = execFileSync('bash', [HOOK], {
    cwd,
    env,
    encoding: 'utf8',
    input: '',
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  return { stdout };
}

test('B: WD→memory dir matches Claude Code [^a-zA-Z0-9]→- encoding (spaces/_)', () => {
  const home = mkdtempSync(join(tmpdir(), 'bsi-home-'));
  const base = mkdtempSync(join(tmpdir(), 'bsi-cwd-'));
  // a cwd that contains a space AND an underscore — the chars the old
  // `sed 's|/|-|g; s|_|-|g'` mis-handles (space left intact = divergence).
  const cwd = join(base, 'has space_dir');
  mkdirSync(cwd, { recursive: true });
  const stateDir = join(home, '.claude', 'channels', 'discord-testbot');
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(join(stateDir, 'soul.md'), '# testbot soul\n');

  const { stdout } = runHook({ cwd, stateDir, home });

  // Assert only on the unique leaf segment so the macOS /var→/private/var
  // symlink in the tmp prefix can't make this fail for the wrong reason.
  // Claude Code's real encoding is [^a-zA-Z0-9]→- (space AND _ → -), so the
  // leaf `has space_dir` must become `has-space-dir`.
  assert.match(
    stdout,
    /has-space-dir\/memory/,
    'leaf `has space_dir` must encode to `has-space-dir` ([^a-zA-Z0-9]→-)',
  );
  assert.doesNotMatch(
    stdout,
    /has space-dir|has-space_dir|has space_dir/,
    'old `sed s|/|-|g; s|_|-|g` leaves the space (divergence from Claude Code)',
  );
  rmSync(home, { recursive: true, force: true });
  rmSync(base, { recursive: true, force: true });
});

test('C: bare `discord` state dir does not mis-inject discord-discord MISSING soul', () => {
  const home = mkdtempSync(join(tmpdir(), 'bsi-home-'));
  const cwd = mkdtempSync(join(tmpdir(), 'bsi-cwd-'));
  // ~/.claude/channels/discord  (the stock plugin dir, NO per-bot suffix)
  const stateDir = join(home, '.claude', 'channels', 'discord');
  mkdirSync(stateDir, { recursive: true });

  const { stdout } = runHook({ cwd, stateDir, home });

  assert.doesNotMatch(
    stdout,
    /discord-discord/,
    'a bare `discord` dir must not resolve BOT=discord → discord-discord/soul.md',
  );
  assert.doesNotMatch(
    stdout,
    /soul\.md:?\s*MISSING/i,
    'must not inject a MISSING soul placeholder for a non-per-bot session',
  );
  rmSync(home, { recursive: true, force: true });
  rmSync(cwd, { recursive: true, force: true });
});

test('D: workspace-local shared-memory/SHARED-INDEX.md is detected without env vars', () => {
  const home = mkdtempSync(join(tmpdir(), 'bsi-home-'));
  const cwd = mkdtempSync(join(tmpdir(), 'bsi-cwd-'));
  // a real per-bot session so the hook proceeds to the shared-memory section
  const stateDir = join(home, '.claude', 'channels', 'discord-testbot');
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(join(stateDir, 'soul.md'), '# testbot soul\n');
  // claude-discode workspace layout: shared-memory/ next to the cwd, no env var
  mkdirSync(join(cwd, 'shared-memory'), { recursive: true });
  writeFileSync(
    join(cwd, 'shared-memory', 'SHARED-INDEX.md'),
    '# SHARED-INDEX\nWORKSPACE_LOCAL_SHARED_MARKER\n',
  );

  const { stdout } = runHook({ cwd, stateDir, home });

  // The hook JSON-escapes non-ASCII (json.dumps default), so assert on the
  // ASCII path + content marker rather than the Korean section header.
  assert.match(
    stdout,
    /shared-memory\/SHARED-INDEX\.md/,
    'workspace-local shared-memory path must be the injected source (finding D)',
  );
  assert.match(
    stdout,
    /WORKSPACE_LOCAL_SHARED_MARKER/,
    'the workspace-local index content must be injected',
  );
  rmSync(home, { recursive: true, force: true });
  rmSync(cwd, { recursive: true, force: true });
});

// B3 (PRD 59-pm-prd-night-batch success criteria 4-5): rules-seed.md carries a
// version stamp, and when the bot WD's copy is older than the product-bundled
// templates/rules-seed.md, the SessionStart hook prints a boot-time WARN — on
// stderr only (stdout is reserved for the JSON hookSpecificOutput contract),
// and it never touches (auto-merges/auto-updates) the bot's own file.
//
// Fixture: a self-contained fake plugin root (hooks/ + templates/) so this
// test never depends on the real repo's current templates/rules-seed.md
// version. _PLUGIN_ROOT inside the hook is derived from the invoked script's
// own path (dirname($0)/..), so copying the hook into fakeRoot/hooks/ and
// running it from there resolves _PLUGIN_ROOT to fakeRoot.
function makeFakePluginRoot(productRulesSeedVersion) {
  const fakeRoot = mkdtempSync(join(tmpdir(), 'bsi-root-'));
  mkdirSync(join(fakeRoot, 'hooks'), { recursive: true });
  mkdirSync(join(fakeRoot, 'templates'), { recursive: true });
  copyFileSync(HOOK, join(fakeRoot, 'hooks', 'bot-session-init.sh'));
  writeFileSync(join(fakeRoot, 'templates', 'rules-seed.md'), `<!-- rules-seed ${productRulesSeedVersion} -->\n`);
  return fakeRoot;
}

function runFakeHook(fakeRoot, { cwd, home, stateDir, botWd }) {
  return spawnSync('bash', [join(fakeRoot, 'hooks', 'bot-session-init.sh')], {
    cwd,
    env: { PATH: process.env.PATH, HOME: home, DISCORD_STATE_DIR: stateDir, BOT_WD: botWd },
    encoding: 'utf8',
    input: '',
  });
}

test('B3: rules-seed staleness prints a WARN on stderr (never stdout) when the bot WD copy is older', () => {
  const fakeRoot = makeFakePluginRoot('v1.0.0');
  const home = mkdtempSync(join(tmpdir(), 'bsi-home-'));
  const cwd = mkdtempSync(join(tmpdir(), 'bsi-cwd-'));
  const botWd = mkdtempSync(join(tmpdir(), 'bsi-botwd-'));
  const stateDir = join(home, '.claude', 'channels', 'discord-testbot');
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(join(stateDir, 'soul.md'), '# testbot soul\n');
  writeFileSync(join(botWd, 'rules-seed.md'), '<!-- rules-seed v0.9.0 -->\ncustomized by operator\n');

  const result = runFakeHook(fakeRoot, { cwd, home, stateDir, botWd });

  assert.match(
    result.stderr,
    /\[thiscode\]\[WARN\] rules-seed v0\.9\.0 -> v1\.0\.0 available — update by explicit command only/,
  );
  assert.doesNotMatch(result.stdout, /WARN/, 'the WARN must not leak into the JSON hookSpecificOutput stdout');
  rmSync(fakeRoot, { recursive: true, force: true });
  rmSync(home, { recursive: true, force: true });
  rmSync(cwd, { recursive: true, force: true });
  rmSync(botWd, { recursive: true, force: true });
});

test('B3: rules-seed staleness check is silent when the bot WD copy matches the product version', () => {
  const fakeRoot = makeFakePluginRoot('v1.0.0');
  const home = mkdtempSync(join(tmpdir(), 'bsi-home-'));
  const cwd = mkdtempSync(join(tmpdir(), 'bsi-cwd-'));
  const botWd = mkdtempSync(join(tmpdir(), 'bsi-botwd-'));
  const stateDir = join(home, '.claude', 'channels', 'discord-testbot');
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(join(stateDir, 'soul.md'), '# testbot soul\n');
  writeFileSync(join(botWd, 'rules-seed.md'), '<!-- rules-seed v1.0.0 -->\n');

  const result = runFakeHook(fakeRoot, { cwd, home, stateDir, botWd });

  assert.doesNotMatch(result.stderr, /WARN/);
  rmSync(fakeRoot, { recursive: true, force: true });
  rmSync(home, { recursive: true, force: true });
  rmSync(cwd, { recursive: true, force: true });
  rmSync(botWd, { recursive: true, force: true });
});

test('B3: rules-seed staleness check never auto-merges — the bot WD copy is untouched by the hook', () => {
  const fakeRoot = makeFakePluginRoot('v1.0.0');
  const home = mkdtempSync(join(tmpdir(), 'bsi-home-'));
  const cwd = mkdtempSync(join(tmpdir(), 'bsi-cwd-'));
  const botWd = mkdtempSync(join(tmpdir(), 'bsi-botwd-'));
  const stateDir = join(home, '.claude', 'channels', 'discord-testbot');
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(join(stateDir, 'soul.md'), '# testbot soul\n');
  const before = '<!-- rules-seed v0.9.0 -->\ncustomized by operator\n';
  writeFileSync(join(botWd, 'rules-seed.md'), before);

  runFakeHook(fakeRoot, { cwd, home, stateDir, botWd });

  assert.equal(readFileSync(join(botWd, 'rules-seed.md'), 'utf8'), before);
  rmSync(fakeRoot, { recursive: true, force: true });
  rmSync(home, { recursive: true, force: true });
  rmSync(cwd, { recursive: true, force: true });
  rmSync(botWd, { recursive: true, force: true });
});

test('B3: rules-seed staleness check skips silently (no crash, exit 0) when the bot WD has no rules-seed.md yet', () => {
  const fakeRoot = makeFakePluginRoot('v1.0.0');
  const home = mkdtempSync(join(tmpdir(), 'bsi-home-'));
  const cwd = mkdtempSync(join(tmpdir(), 'bsi-cwd-'));
  const botWd = mkdtempSync(join(tmpdir(), 'bsi-botwd-'));
  const stateDir = join(home, '.claude', 'channels', 'discord-testbot');
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(join(stateDir, 'soul.md'), '# testbot soul\n');
  // deliberately no rules-seed.md under botWd

  const result = runFakeHook(fakeRoot, { cwd, home, stateDir, botWd });

  assert.equal(result.status, 0);
  assert.doesNotMatch(result.stderr, /WARN/);
  rmSync(fakeRoot, { recursive: true, force: true });
  rmSync(home, { recursive: true, force: true });
  rmSync(cwd, { recursive: true, force: true });
  rmSync(botWd, { recursive: true, force: true });
});
