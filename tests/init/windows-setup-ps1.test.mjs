// Execution tests for windows-setup.ps1 Step state transitions + policy judgment.
// The lib block and the real ExecutionPolicy Step (between their markers) are
// extracted from the actual script and run in EVERY available PowerShell engine
// (pwsh AND Windows PowerShell 5.1) with mock bodies/cmdlets — the script IS the
// tested artifact, and on Windows CI both engines execute (round-4: 5.1 coverage).
// Skips when no engine exists (plain macOS dev box); GitHub-hosted runners all
// ship pwsh, windows-latest additionally ships powershell 5.1.
// (2026-07-21 post-review rounds 3-4: HIGH-3 durable fixtures)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';

const SRC = readFileSync(new URL('../../scripts/windows-setup.ps1', import.meta.url), 'utf8')
  .replace(/^﻿/, '').replace(/\r\n/g, '\n');

const libM = SRC.match(/# --- thiscode-setup-lib start[\s\S]*?---\n([\s\S]*?)# --- thiscode-setup-lib end ---/);
assert.ok(libM, 'lib markers not found in windows-setup.ps1');
const LIB = libM[1];

const stepM = SRC.match(/# --- thiscode-policy-step start[\s\S]*?---\n([\s\S]*?)# --- thiscode-policy-step end ---/);
assert.ok(stepM, 'policy-step markers not found in windows-setup.ps1');
const POLICY_STEP = stepM[1];

// round-4: run on EVERY available engine, not just the first one.
const ENGINES = ['pwsh', 'powershell'].filter(
  (exe) => spawnSync(exe, ['-NoProfile', '-Command', 'exit 0']).status === 0,
);
const skip = ENGINES.length === 0 && 'no PowerShell runtime (pwsh/powershell) on this machine';

const dir = mkdtempSync(join(tmpdir(), 'ws-ps1-'));
let scenSeq = 0;

function runPs(engine, scenario) {
  const file = join(dir, `scen-${scenSeq++}.ps1`);
  writeFileSync(file, '﻿' + ['$report = [ordered]@{}', LIB, scenario].join('\n'), 'utf8');
  return spawnSync(engine, ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', file], { encoding: 'utf8' });
}

function eachEngine(fn) {
  for (const engine of ENGINES) fn(engine);
}

test('engines: log versions actually executing (evidence of 5.1 vs 7 coverage)', { skip }, () => {
  eachEngine((engine) => {
    const r = spawnSync(engine, ['-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()'], { encoding: 'utf8' });
    assert.equal(r.status, 0, r.stderr);
    console.log(`  [ps-engine] ${engine} = ${r.stdout.trim()}`);
  });
});

test('Step: throwing body → MANUAL_REQUIRED (never OK)', { skip }, () => {
  eachEngine((engine) => {
    const r = runPs(engine, `
Step 'boom' { throw "kaput" } 'manual-cmd'
Write-Output ("STATUS=" + $report['boom'])`);
    assert.equal(r.status, 0, `${engine}: ${r.stderr}`);
    assert.match(r.stdout, /STATUS=MANUAL_REQUIRED: manual-cmd/, engine);
  });
});

test('Step: body sets PENDING_RESTART via StepStatus channel', { skip }, () => {
  eachEngine((engine) => {
    const r = runPs(engine, `
Step 'pend' { $script:StepStatus = 'PENDING_RESTART' } 'x'
Write-Output ("STATUS=" + $report['pend'])`);
    assert.equal(r.status, 0, `${engine}: ${r.stderr}`);
    assert.match(r.stdout, /STATUS=PENDING_RESTART/, engine);
  });
});

test('Step: native stdout noise does not pollute status (defaults OK)', { skip }, () => {
  eachEngine((engine) => {
    const r = runPs(engine, `
Step 'noisy' { Write-Output "lots"; Write-Output "of installer output" } 'x'
Write-Output ("STATUS=" + $report['noisy'])`);
    assert.equal(r.status, 0, `${engine}: ${r.stderr}`);
    assert.match(r.stdout, /STATUS=OK\b/, engine);
  });
});

test('Step: non-terminating cmdlet error inside body → MANUAL_REQUIRED (EAP=Stop promotion)', { skip }, () => {
  eachEngine((engine) => {
    const r = runPs(engine, `
Step 'nonterm' { Get-Item '/definitely/not/here-xyz' } 'manual-b'
Write-Output ("STATUS=" + $report['nonterm'])`);
    assert.equal(r.status, 0, `${engine}: ${r.stderr}`);
    assert.match(r.stdout, /STATUS=MANUAL_REQUIRED: manual-b/, engine);
  });
});

// ---- policy helper matrix (incl. round-4 precedence counterexample) ----

const POLICY_CASES = [
  { machine: 'Restricted',   user: 'Undefined', expect: 'MachinePolicy', why: 'machine GPO blocks' },
  { machine: 'Undefined',    user: 'AllSigned', expect: 'UserPolicy',    why: 'user GPO blocks when machine undefined' },
  { machine: 'RemoteSigned', user: 'AllSigned', expect: '',              why: 'defined-permissive MachinePolicy wins — UserPolicy never evaluated (round-4 counterexample)' },
  { machine: 'Undefined',    user: 'Undefined', expect: '',              why: 'no GPO override' },
];

for (const c of POLICY_CASES) {
  test(`policy: Machine=${c.machine} User=${c.user} → '${c.expect || 'null'}' (${c.why})`, { skip }, () => {
    eachEngine((engine) => {
      const r = runPs(engine, `
$s = Get-PolicyOverrideScope -MachinePolicy '${c.machine}' -UserPolicy '${c.user}'
Write-Output ("SCOPE=[" + $s + "]")`);
      assert.equal(r.status, 0, `${engine}: ${r.stderr}`);
      assert.match(r.stdout, new RegExp(`SCOPE=\\[${c.expect}\\]`), engine);
    });
  });
}

// ---- integrated path: real ExecutionPolicy Step → report (round-4 item 3) ----
// Get-/Set-ExecutionPolicy are shadowed by functions (functions take precedence
// over cmdlets), so the REAL Step body from the script runs against a mocked
// policy matrix without touching the machine.

function runPolicyStep(engine, machine, user) {
  return runPs(engine, `
function Set-ExecutionPolicy { param($Scope, $ExecutionPolicy) ; $true | Out-Null }
function Get-ExecutionPolicy {
  param($Scope)
  switch ($Scope) {
    'CurrentUser'   { 'RemoteSigned' }
    'MachinePolicy' { '${machine}' }
    'UserPolicy'    { '${user}' }
    default         { 'RemoteSigned' }
  }
}
${POLICY_STEP}
Write-Output ("REPORT=[" + $report['ExecutionPolicy (프로필 로드 전제)'] + "]")`);
}

test('integrated: blocked UserPolicy flows through real Step into report as MANUAL_REQUIRED', { skip }, () => {
  eachEngine((engine) => {
    const r = runPolicyStep(engine, 'Undefined', 'AllSigned');
    assert.equal(r.status, 0, `${engine}: ${r.stderr}`);
    assert.match(r.stdout, /REPORT=\[MANUAL_REQUIRED: [^\]]*UserPolicy[^\]]*\]/, engine);
  });
});

test('integrated: permissive MachinePolicy overrides blocking UserPolicy → OK (no false MANUAL_REQUIRED)', { skip }, () => {
  eachEngine((engine) => {
    const r = runPolicyStep(engine, 'RemoteSigned', 'AllSigned');
    assert.equal(r.status, 0, `${engine}: ${r.stderr}`);
    assert.match(r.stdout, /REPORT=\[OK\]/, engine);
  });
});

test('integrated: no GPO → OK', { skip }, () => {
  eachEngine((engine) => {
    const r = runPolicyStep(engine, 'Undefined', 'Undefined');
    assert.equal(r.status, 0, `${engine}: ${r.stderr}`);
    assert.match(r.stdout, /REPORT=\[OK\]/, engine);
  });
});

test('prescription: GPO guidance asks IT admin, never suggests Bypass as the fix', () => {
  const guidance = SRC.match(/if \(\$blocked\) \{[\s\S]*?\n  \}/);
  assert.ok(guidance, 'blocked-policy branch not found');
  assert.match(guidance[0], /IT 관리자/);
  assert.doesNotMatch(guidance[0], /Bypass/);
});
