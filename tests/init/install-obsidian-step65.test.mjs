import assert from 'node:assert/strict';
import {
  chmodSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const repoRoot = resolve(import.meta.dirname, '../..');
const installScript = join(repoRoot, 'install.sh');

function runStep65(env, timeout = 8_000) {
  return spawnSync(
    '/bin/bash',
    ['-c', 'THISCODE_INSTALL_SH_SOURCE_ONLY=1 source "$1"; install_obsidian_cli', 'bash', installScript],
    { env, encoding: 'utf8', timeout },
  );
}

function makeFakeObsidian(root, body) {
  const bin = join(root, 'bin');
  mkdirSync(bin, { recursive: true });
  const fake = join(bin, 'obsidian');
  writeFileSync(fake, `#!/usr/bin/env bash\n${body}\n`);
  chmodSync(fake, 0o755);
  return bin;
}

test('Step 6.5 detects the installed macOS Obsidian app without a version probe', { skip: process.platform !== 'darwin' }, () => {
  const result = runStep65({ ...process.env, ENV_KIND: 'macos' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Obsidian 앱 감지\(버전 미확인\)/);
  assert.doesNotMatch(result.stdout, /Obsidian CLI already installed:/);
});

test('Step 6.5 never invokes a Homebrew cask Obsidian wrapper', (t) => {
  const root = mkdtempSync(join(tmpdir(), 'thiscode-step65-cask-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const caskDir = join(root, 'Caskroom', 'obsidian', '1.0');
  const bin = join(root, 'bin');
  const marker = join(root, 'called');
  mkdirSync(caskDir, { recursive: true });
  mkdirSync(bin);
  const wrapper = join(caskDir, 'obsidian.wrapper.sh');
  writeFileSync(wrapper, `#!/usr/bin/env bash\n: > '${marker}'\n`);
  chmodSync(wrapper, 0o755);
  symlinkSync(wrapper, join(bin, 'obsidian'));

  const result = runStep65({ PATH: `${bin}:/usr/bin:/bin`, ENV_KIND: 'macos' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Obsidian 앱 감지\(버전 미확인\)/);
  assert.equal(existsSync(marker), false);
});

test('Step 6.5 keeps the no-Obsidian fallback when the command is absent', () => {
  const result = runStep65({ PATH: '/usr/bin:/bin', ENV_KIND: 'linux' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Obsidian CLI not installed/);
  assert.match(result.stdout, /skipping this step is fine/);
});

test('Step 6.5 reports a non-GUI CLI version', (t) => {
  const root = mkdtempSync(join(tmpdir(), 'thiscode-step65-cli-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const bin = makeFakeObsidian(root, "printf 'obsidian-cli 1.2.3\\n'");

  const result = runStep65({ PATH: `${bin}:/usr/bin:/bin`, ENV_KIND: 'macos' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Obsidian CLI already installed: obsidian-cli 1\.2\.3/);
});

test('Step 6.5 kills a non-GUI version probe after five seconds', (t) => {
  const root = mkdtempSync(join(tmpdir(), 'thiscode-step65-hang-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const bin = makeFakeObsidian(root, 'exec sleep 30');
  const started = Date.now();

  const result = runStep65({ PATH: `${bin}:/usr/bin:/bin`, ENV_KIND: 'macos' });
  const elapsedMs = Date.now() - started;
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /버전 확인 5초 초과/);
  assert.ok(elapsedMs >= 4_500 && elapsedMs < 7_500, `elapsed=${elapsedMs}ms`);
});
