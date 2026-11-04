// tests/init/browser-detect.test.mjs
// Contract: ThisCode picks ego lite → Aside → fallback with no user setup step.
// Each case uses a throw-away home folder + PATH holding fake `ego-browser` / `aside` shell programs.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { detectBrowser } from '../../scripts/lib/browser-detect.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const CLI = join(ROOT, 'scripts', 'browser-detect.mjs');
const isWin = process.platform === 'win32';

const EGO_OK = '#!/bin/sh\nif [ "$1" = skill ]; then echo "[ego-browser:skill] guide"; echo "[ego-browser:skill] end of guide v2.2.0"; fi\nexit 0\n';
const EGO_BROKEN = '#!/bin/sh\necho "cannot connect" >&2\nexit 3\n';
const EGO_HANG = '#!/bin/sh\nsleep 30\n';
const ASIDE_OK = '#!/bin/sh\nif [ "$1" = --version ]; then echo 1.26.0; fi\nexit 0\n';

function sandbox() {
  const root = mkdtempSync(join(tmpdir(), 'tc-browser-'));
  const home = join(root, 'home');
  const bin = join(root, 'bin');
  mkdirSync(home, { recursive: true });
  mkdirSync(bin, { recursive: true });
  const put = (dir, rel, body) => {
    const p = join(dir, rel);
    mkdirSync(dirname(p), { recursive: true });
    writeFileSync(p, body);
    chmodSync(p, 0o755);
    return p;
  };
  const env = { HOME: home, PATH: `${bin}:/usr/bin:/bin` };
  return {
    home, bin, env,
    onPath: (name, body) => put(bin, name, body),
    inHome: (rel, body) => put(home, rel, body),
    detect: (opts = {}) => detectBrowser({ env, home, ...opts }),
    done: () => rmSync(root, { recursive: true, force: true }),
  };
}

const skip = isWin ? 'fake shell programs need a POSIX shell' : false;

test('1 ego lite only → ego', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('ego-browser', EGO_OK);
    const d = s.detect();
    assert.equal(d.provider, 'ego');
    assert.ok(d.bin.endsWith('ego-browser'));
    assert.equal(d.detected.aside.found, false);
  } finally { s.done(); }
});

test('2 Aside only → aside', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('aside', ASIDE_OK);
    const d = s.detect();
    assert.equal(d.provider, 'aside');
    assert.equal(d.detected.ego.found, false);
  } finally { s.done(); }
});

test('3 both → ego first', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('ego-browser', EGO_OK);
    s.onPath('aside', ASIDE_OK);
    const d = s.detect();
    assert.equal(d.provider, 'ego');
    assert.equal(d.detected.aside.ready, true);
  } finally { s.done(); }
});

test('4 neither → fallback (existing MCP / Playwright path)', { skip }, () => {
  const s = sandbox();
  try {
    const d = s.detect();
    assert.equal(d.provider, 'fallback');
    assert.equal(d.bin, null);
    assert.deepEqual(d.order, ['ego', 'aside', 'fallback']);
  } finally { s.done(); }
});

test('ego lite in ~/.local/bin but not on PATH → found, absolute path', { skip }, () => {
  const s = sandbox();
  try {
    const p = s.inHome('.local/bin/ego-browser', EGO_OK);
    const d = s.detect();
    assert.equal(d.provider, 'ego');
    assert.equal(d.bin, p);
  } finally { s.done(); }
});

test('Aside CLI inside the app folder (space in path) → aside', { skip }, () => {
  const s = sandbox();
  try {
    s.inHome('.aside/cli/Aside CLI.app/Contents/MacOS/aside', ASIDE_OK);
    const d = s.detect();
    assert.equal(d.provider, 'aside');
    assert.match(d.bin, /Aside CLI\.app/);
  } finally { s.done(); }
});

test('ego installed but not answering → Aside (negative pair)', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('ego-browser', EGO_BROKEN);
    s.onPath('aside', ASIDE_OK);
    const d = s.detect();
    assert.equal(d.provider, 'aside');
    assert.equal(d.detected.ego.found, true);
    assert.equal(d.detected.ego.ready, false);
  } finally { s.done(); }
});

test('a hanging ego probe times out instead of stalling', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('ego-browser', EGO_HANG);
    const t0 = Date.now();
    const d = s.detect({ timeoutMs: 1000 });
    assert.ok(Date.now() - t0 < 10000);
    assert.equal(d.detected.ego.why, 'probe timeout');
    assert.equal(d.provider, 'fallback');
  } finally { s.done(); }
});

test('Aside installed but not answering → fallback (negative pair)', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('aside', EGO_BROKEN);
    const d = s.detect();
    assert.equal(d.provider, 'fallback');
    assert.equal(d.detected.aside.found, true);
    assert.equal(d.detected.aside.ready, false);
  } finally { s.done(); }
});

test('ego guide without its last line → not ready', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('ego-browser', '#!/bin/sh\necho "[ego-browser:skill] guide (cut)"\nexit 0\n');
    const d = s.detect();
    assert.equal(d.provider, 'fallback');
    assert.equal(d.detected.ego.why, 'guide incomplete');
  } finally { s.done(); }
});

test('exit code alone decides: output looks fine but non-zero exit → not ready', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('aside', '#!/bin/sh\necho 1.26.0\nexit 7\n');
    s.onPath('ego-browser', '#!/bin/sh\necho "[ego-browser:skill] end of guide v2.2.0"\nexit 5\n');
    const d = s.detect();
    assert.equal(d.provider, 'fallback');
    assert.equal(d.detected.aside.why, 'probe exit 7');
    assert.equal(d.detected.ego.why, 'probe exit 5');
  } finally { s.done(); }
});

test('both hanging → fallback within the time limit', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('ego-browser', EGO_HANG);
    s.onPath('aside', EGO_HANG);
    const t0 = Date.now();
    const d = s.detect({ timeoutMs: 1000 });
    assert.ok(Date.now() - t0 < 15000);
    assert.equal(d.provider, 'fallback');
    assert.equal(d.detected.aside.why, 'probe timeout');
  } finally { s.done(); }
});

test('prefer aside: used when present, ego when Aside is missing', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('ego-browser', EGO_OK);
    assert.equal(s.detect({ prefer: 'aside' }).provider, 'ego');
    s.onPath('aside', ASIDE_OK);
    assert.equal(s.detect({ prefer: 'aside' }).provider, 'aside');
  } finally { s.done(); }
});

test('CLI prints one JSON line and --get provider', { skip }, () => {
  const s = sandbox();
  try {
    s.onPath('aside', ASIDE_OK);
    const j = spawnSync(process.execPath, [CLI], { env: s.env, encoding: 'utf8' });
    assert.equal(j.status, 0);
    assert.equal(JSON.parse(j.stdout).provider, 'aside');
    const g = spawnSync(process.execPath, [CLI, '--get', 'provider'], { env: s.env, encoding: 'utf8' });
    assert.equal(g.stdout.trim(), 'aside');
    const bad = spawnSync(process.execPath, [CLI, '--nope'], { env: s.env, encoding: 'utf8' });
    assert.equal(bad.status, 2);
  } finally { s.done(); }
});
