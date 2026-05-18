// ⓒ Stop-hook debugging surface (spec §10.1). hooks/stop-debug-surface.sh —
// maintainer's "stop hook으로 디버깅" idea, built SAFE: it is fail-OPEN — it
// ALWAYS exits 0 and can NEVER deny session end (contrast with the existing
// fail-CLOSED stop-pending-task-check.sh). It only *surfaces* (stderr) that a
// session is ending with uncommitted source/test work. RED→GREEN.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HOOK = fileURLToPath(new URL('../../hooks/stop-debug-surface.sh', import.meta.url));

function runHook({ cwd, stdin = '' }) {
  const r = spawnSync('bash', [HOOK], {
    cwd,
    input: stdin,
    encoding: 'utf8',
    env: { ...process.env },
  });
  return { code: r.status, stdout: r.stdout ?? '', stderr: r.stderr ?? '' };
}

function gitInit(dir) {
  for (const args of [
    ['init', '-q'],
    ['config', 'user.email', 't@t'],
    ['config', 'user.name', 't'],
    ['config', 'commit.gpgsign', 'false'],
  ]) {
    spawnSync('git', args, { cwd: dir });
  }
}
function gitCommitAll(dir) {
  spawnSync('git', ['add', '-A'], { cwd: dir });
  spawnSync('git', ['commit', '-q', '-m', 'init'], { cwd: dir });
}

test('SAFETY: never exits 2 — uncommitted source change → advisory on stderr, exit 0', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sds-'));
  gitInit(dir);
  writeFileSync(join(dir, 'thing.sh'), '#!/usr/bin/env bash\necho hi\n');
  gitCommitAll(dir);
  writeFileSync(join(dir, 'thing.sh'), '#!/usr/bin/env bash\necho changed\n'); // uncommitted

  const r = runHook({ cwd: dir, stdin: JSON.stringify({ hook_event_name: 'Stop' }) });
  assert.equal(r.code, 0, 'fail-OPEN: must exit 0, NEVER 2 (must not deny session end)');
  assert.notEqual(r.code, 2, 'a Stop hook that can deny session end is the forbidden design');
  assert.match(
    r.stderr,
    /uncommitted|debug|unsaved/i,
    'must surface the uncommitted debug work on stderr',
  );
  assert.match(r.stderr, /thing\.sh/, 'should name the changed source/test file');
  rmSync(dir, { recursive: true, force: true });
});

test('clean git repo → silent, exit 0', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sds-'));
  gitInit(dir);
  writeFileSync(join(dir, 'thing.sh'), 'echo hi\n');
  gitCommitAll(dir);

  const r = runHook({ cwd: dir, stdin: JSON.stringify({ hook_event_name: 'Stop' }) });
  assert.equal(r.code, 0);
  assert.equal(r.stderr.trim(), '', 'no advisory when nothing uncommitted');
  rmSync(dir, { recursive: true, force: true });
});

test('non-git dir → silent, exit 0 (no git, nothing to surface)', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sds-'));
  writeFileSync(join(dir, 'thing.sh'), 'echo hi\n');
  const r = runHook({ cwd: dir, stdin: JSON.stringify({ hook_event_name: 'Stop' }) });
  assert.equal(r.code, 0);
  assert.equal(r.stderr.trim(), '', 'silent outside a git repo');
  rmSync(dir, { recursive: true, force: true });
});

test('recursion guard: stop_hook_active=true → silent, exit 0', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sds-'));
  gitInit(dir);
  writeFileSync(join(dir, 'x.mjs'), 'export const a=1\n');
  gitCommitAll(dir);
  writeFileSync(join(dir, 'x.mjs'), 'export const a=2\n'); // uncommitted

  const r = runHook({
    cwd: dir,
    stdin: JSON.stringify({ hook_event_name: 'Stop', stop_hook_active: true }),
  });
  assert.equal(r.code, 0);
  assert.equal(r.stderr.trim(), '', 'must not re-fire while a Stop hook is already active');
  rmSync(dir, { recursive: true, force: true });
});

test('non-Stop event → silent, exit 0', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sds-'));
  const r = runHook({ cwd: dir, stdin: JSON.stringify({ hook_event_name: 'SessionStart' }) });
  assert.equal(r.code, 0);
  assert.equal(r.stderr.trim(), '');
  rmSync(dir, { recursive: true, force: true });
});
