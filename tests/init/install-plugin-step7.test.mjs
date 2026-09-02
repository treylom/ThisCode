import assert from 'node:assert/strict';
import {
  chmodSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const repoRoot = resolve(import.meta.dirname, '../..');
const installScript = join(repoRoot, 'install.sh');

function makeFakeClaude(root) {
  const bin = join(root, 'bin');
  mkdirSync(bin, { recursive: true });
  const fake = join(bin, 'claude');
  writeFileSync(fake, `#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >> "$FAKE_CLAUDE_LOG"
case "$1 $2" in
  "plugin list")
    if [ -f "$FAKE_CLAUDE_STATE" ]; then
      printf '%s\\n' '[{"id":"thiscode@thiscode-marketplace","scope":"user","enabled":true}]'
    else
      printf '%s\\n' '[]'
    fi
    ;;
  "plugin marketplace")
    [ "$3" = "add" ]
    printf '%s\\n' "$*" | grep -q -- '--scope user'
    if [ "\${FAKE_CLAUDE_FAIL_ADD:-0}" = "1" ]; then
      echo 'network unavailable' >&2
      exit 42
    fi
    ;;
  "plugin install")
    printf '%s\\n' "$*" | grep -q -- '--scope user'
    printf '%s\\n' "$*" | grep -q -- '--yes'
    if [ "\${FAKE_CLAUDE_FAIL_INSTALL:-0}" = "1" ]; then
      echo 'archive verification failed' >&2
      exit 43
    fi
    : > "$FAKE_CLAUDE_STATE"
    ;;
  *)
    echo "unexpected claude args: $*" >&2
    exit 99
    ;;
esac
`);
  chmodSync(fake, 0o755);
  return bin;
}

function runStep7(env) {
  return spawnSync(
    '/bin/bash',
    ['-c', 'THISCODE_INSTALL_SH_SOURCE_ONLY=1 source "$1"; install_plugin', 'bash', installScript],
    { env, encoding: 'utf8' },
  );
}

function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'thiscode-step7-'));
  const log = join(root, 'claude.log');
  const state = join(root, 'installed');
  writeFileSync(log, '');
  const bin = makeFakeClaude(root);
  const env = {
    ...process.env,
    PATH: `${bin}:${process.env.PATH}`,
    FAKE_CLAUDE_LOG: log,
    FAKE_CLAUDE_STATE: state,
  };
  return { root, log, state, env };
}

test('Step 7 installs at user scope, verifies registry, then skips idempotently', (t) => {
  const f = fixture();
  t.after(() => rmSync(f.root, { recursive: true, force: true }));

  const first = runStep7(f.env);
  assert.equal(first.status, 0, first.stderr);
  assert.match(first.stdout, /installed and verified \(scope: user\)/);

  const firstLog = readFileSync(f.log, 'utf8');
  assert.match(firstLog, /plugin marketplace add treylom\/ThisCode --scope user/);
  assert.match(firstLog, /plugin install thiscode@thiscode-marketplace --scope user --yes/);

  writeFileSync(f.log, '');
  const second = runStep7(f.env);
  assert.equal(second.status, 0, second.stderr);
  assert.match(second.stdout, /already installed \(scope: user\) → skip/);
  assert.equal(readFileSync(f.log, 'utf8').trim(), 'plugin list --json');
});

test('Step 7 preserves the manual fallback when claude is absent', (t) => {
  const root = mkdtempSync(join(tmpdir(), 'thiscode-step7-no-claude-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const bin = join(root, 'bin');
  mkdirSync(bin);
  symlinkSync('/bin/cat', join(bin, 'cat'));

  const result = runStep7({ PATH: bin });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Claude Code executable was not found in PATH/);
  assert.match(result.stdout, /\/plugin marketplace add treylom\/ThisCode/);
  assert.match(result.stdout, /\/plugin install thiscode@thiscode-marketplace/);
});

test('Step 7 reports a marketplace failure reason before the manual fallback', (t) => {
  const f = fixture();
  t.after(() => rmSync(f.root, { recursive: true, force: true }));

  const result = runStep7({ ...f.env, FAKE_CLAUDE_FAIL_ADD: '1' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /could not finish: network unavailable/);
  assert.match(result.stdout, /Manual fallback/);
});

test('Step 7 reports an install failure reason before the manual fallback', (t) => {
  const f = fixture();
  t.after(() => rmSync(f.root, { recursive: true, force: true }));

  const result = runStep7({ ...f.env, FAKE_CLAUDE_FAIL_INSTALL: '1' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /could not finish: archive verification failed/);
  assert.match(result.stdout, /Manual fallback/);
});
