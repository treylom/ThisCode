// Contract tests for the install-hooks settings merge (jq path + node fallback).
// The snippets are extracted from scripts/install-hooks.sh so the SCRIPT IS the
// tested artifact — no drift between the shipped installer and verified behavior.
// (Before 2026-09-03 these came from skills/install-hooks/SKILL.md; the merge
//  logic moved into the script so install-hooks and create-bot share one copy.)
// Contract: (1) no hook loss (2) first-occurrence order preserved
// (3) idempotent re-run (4) node/jq parity. (2026-07-21 post-review HIGH-2)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';

const DOC = readFileSync(new URL('../../scripts/install-hooks.sh', import.meta.url), 'utf8').replace(/\r\n/g, '\n'); // Windows CRLF checkout

function extractJq() {
  const m = DOC.match(/jq -s '(def uniqHooks:[\s\S]*?)' \\\n {4}"\$SETTINGS"/);
  assert.ok(m, 'jq merge expression not found in scripts/install-hooks.sh');
  return m[1];
}

function extractNode() {
  // `const a = JSON.parse` 로 시작하는 «병합» 스크립트만 — 같은 파일의 조회용
  // node 한 줄들(let j={} 로 시작)과 구별하지 않으면 그 사이 전체를 삼킨다.
  const m = DOC.match(/node -e '(const fs=require\("fs"\);\nconst a = JSON\.parse[\s\S]*?)' "\$SETTINGS" "\$PATCH" "\$SETTINGS\.tmp"/);
  assert.ok(m, 'node fallback snippet not found in scripts/install-hooks.sh');
  return m[1];
}

const EXISTING = {
  model: 'opus',
  hooks: { SessionStart: [{ matcher: '', hooks: [
    { type: 'command', command: 'z.sh', timeout: 5 },
    { type: 'command', command: 'a.sh', timeout: 5 },
  ] }] },
};
const PATCH = {
  hooks: {
    SessionStart: [{ matcher: '', hooks: [
      { type: 'command', command: 'z.sh', timeout: 5 },
      { type: 'command', command: 'm.sh', timeout: 5 },
    ] }],
    Stop: [{ matcher: '', hooks: [{ type: 'command', command: 'stop.sh', timeout: 5 }] }],
  },
};
const EXPECT_SS = ['z.sh', 'a.sh', 'm.sh']; // loss-free + order-preserving + deduped

const dir = mkdtempSync(join(tmpdir(), 'ih-merge-'));
const settingsFile = join(dir, 'settings.json');
const patchFile = join(dir, 'patch.json');
writeFileSync(settingsFile, JSON.stringify(EXISTING));
writeFileSync(patchFile, JSON.stringify(PATCH));

const cmds = (merged) => merged.hooks.SessionStart.flatMap((g) => g.hooks.map((h) => h.command));

function runNode(settingsPath, patchJson) {
  const script = extractNode();
  const scriptFile = join(dir, 'merge.js');
  // the doc snippet reads argv[1]=settings file, argv[2]=patch string, argv[3]=out file
  writeFileSync(scriptFile, script.replace(/process\.argv\[(\d)\]/g, (s, n) => `process.argv[${Number(n) + 1}]`));
  const outFile = join(dir, 'out-node.json');
  const r = spawnSync(process.execPath, [scriptFile, settingsPath, patchJson, outFile], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  return JSON.parse(readFileSync(outFile, 'utf8'));
}

const hasJq = spawnSync('jq', ['--version']).status === 0;

function runJq(settingsPath, patchPath) {
  const r = spawnSync('jq', ['-s', extractJq(), settingsPath, patchPath], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  return JSON.parse(r.stdout);
}

test('node fallback: loss-free, order-preserving, deduped; preserves other settings', () => {
  const merged = runNode(settingsFile, JSON.stringify(PATCH));
  assert.deepEqual(cmds(merged), EXPECT_SS);
  assert.equal(merged.model, 'opus');
  assert.deepEqual(merged.hooks.Stop.flatMap((g) => g.hooks.map((h) => h.command)), ['stop.sh']);
});

test('node fallback: idempotent on re-run', () => {
  const once = runNode(settingsFile, JSON.stringify(PATCH));
  const onceFile = join(dir, 'once.json');
  writeFileSync(onceFile, JSON.stringify(once));
  const twice = runNode(onceFile, JSON.stringify(PATCH));
  assert.deepEqual(cmds(twice), EXPECT_SS);
});

test('jq path: loss-free, order-preserving, deduped — parity with node', { skip: !hasJq && 'jq not installed' }, () => {
  const merged = runJq(settingsFile, patchFile);
  assert.deepEqual(cmds(merged), EXPECT_SS);
  assert.equal(merged.model, 'opus');
});

test('jq path: idempotent on re-run', { skip: !hasJq && 'jq not installed' }, () => {
  const once = runJq(settingsFile, patchFile);
  const onceFile = join(dir, 'once-jq.json');
  writeFileSync(onceFile, JSON.stringify(once));
  const twice = runJq(onceFile, patchFile);
  assert.deepEqual(cmds(twice), EXPECT_SS);
});
