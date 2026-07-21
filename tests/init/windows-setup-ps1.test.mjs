// Execution tests for windows-setup.ps1 Step state transitions + policy judgment.
// The lib block (between the lib markers) is extracted from the actual script and
// run in PowerShell (pwsh or powershell) with mock bodies — the script IS the
// tested artifact. Skips when no PowerShell runtime exists (e.g. plain macOS dev
// box); GitHub-hosted ubuntu/macos/windows runners all ship pwsh, so CI covers it.
// (2026-07-21 post-review round 3: HIGH-3 durable fixtures)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';

const SRC = readFileSync(new URL('../../scripts/windows-setup.ps1', import.meta.url), 'utf8')
  .replace(/^﻿/, '').replace(/\r\n/g, '\n');

const m = SRC.match(/# --- thiscode-setup-lib start[\s\S]*?---\n([\s\S]*?)# --- thiscode-setup-lib end ---/);
assert.ok(m, 'lib markers not found in windows-setup.ps1');
const LIB = m[1];

const PS = ['pwsh', 'powershell'].find((exe) => spawnSync(exe, ['-NoProfile', '-Command', 'exit 0']).status === 0);
const skip = !PS && 'no PowerShell runtime (pwsh/powershell) on this machine';

const dir = mkdtempSync(join(tmpdir(), 'ws-ps1-'));

function runPs(scenario) {
  const file = join(dir, `scen-${Math.random().toString(36).slice(2)}.ps1`);
  writeFileSync(file, '﻿' + ['$report = [ordered]@{}', LIB, scenario].join('\n'), 'utf8');
  const r = spawnSync(PS, ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', file], { encoding: 'utf8' });
  return r;
}

test('Step: throwing body → MANUAL_REQUIRED (never OK)', { skip }, () => {
  const r = runPs(`
Step 'boom' { throw "kaput" } 'manual-cmd'
Write-Output ("STATUS=" + $report['boom'])`);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /STATUS=MANUAL_REQUIRED: manual-cmd/);
});

test('Step: body sets PENDING_RESTART via StepStatus channel', { skip }, () => {
  const r = runPs(`
Step 'pend' { $script:StepStatus = 'PENDING_RESTART' } 'x'
Write-Output ("STATUS=" + $report['pend'])`);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /STATUS=PENDING_RESTART/);
});

test('Step: native stdout noise does not pollute status (defaults OK)', { skip }, () => {
  const r = runPs(`
Step 'noisy' { Write-Output "lots"; Write-Output "of installer output" } 'x'
Write-Output ("STATUS=" + $report['noisy'])`);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /STATUS=OK\b/);
});

test('Step: non-terminating cmdlet error inside body → MANUAL_REQUIRED (EAP=Stop promotion)', { skip }, () => {
  const r = runPs(`
Step 'nonterm' { Get-Item '/definitely/not/here-xyz' } 'manual-b'
Write-Output ("STATUS=" + $report['nonterm'])`);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /STATUS=MANUAL_REQUIRED: manual-b/);
});

test('policy: MachinePolicy Restricted → blocked scope MachinePolicy', { skip }, () => {
  const r = runPs(`Write-Output ("SCOPE=" + (Get-PolicyOverrideScope -MachinePolicy 'Restricted' -UserPolicy 'Undefined'))`);
  assert.match(r.stdout, /SCOPE=MachinePolicy/);
});

test('policy: UserPolicy AllSigned → blocked scope UserPolicy (round-3 gap)', { skip }, () => {
  const r = runPs(`Write-Output ("SCOPE=" + (Get-PolicyOverrideScope -MachinePolicy 'Undefined' -UserPolicy 'AllSigned'))`);
  assert.match(r.stdout, /SCOPE=UserPolicy/);
});

test('policy: no GPO override → not blocked', { skip }, () => {
  const r = runPs(`
$s = Get-PolicyOverrideScope -MachinePolicy 'Undefined' -UserPolicy 'Undefined'
Write-Output ("EMPTY=" + [string]::IsNullOrEmpty($s))`);
  assert.match(r.stdout, /EMPTY=True/);
});

test('prescription: GPO guidance asks IT admin, never suggests Bypass as the fix', () => {
  const guidance = SRC.match(/if \(\$blocked\) \{[\s\S]*?\n  \}/);
  assert.ok(guidance, 'blocked-policy branch not found');
  assert.match(guidance[0], /IT 관리자/);
  assert.doesNotMatch(guidance[0], /Bypass/);
});
