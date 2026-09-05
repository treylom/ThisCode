#!/usr/bin/env node

// Explicit hermetic/fixture shell-test allowlist. Do not replace this with a
// recursive tests/**/*.sh walk: several tracked shell files probe host state,
// live services, or user configuration (see tests/SHELL-TESTS.md).
import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const ROOT = resolve(fileURLToPath(new URL('..', import.meta.url)));

const SAFE_SHELL_TESTS = Object.freeze([
  'tests/agents/test-all-yamls.sh',
  'tests/agents/test-hermes-runtime-manifest.sh',
  'tests/agents/test-index-roundtrip.sh',
  'tests/agents/test-plugin-sync.sh',
  'tests/agents/test-plugin-v2.sh',
  'tests/agents/test-router-yaml.sh',
  'tests/agents/test-schema-validation.sh',
  'tests/benchmark/test-fixtures-shape.sh',
  'tests/benchmark/test-tier-label-v2.sh',
  'tests/benchmark/test-tier-swap.sh',
  'tests/benchmark/test-tier1-skip.sh',
  'tests/benchmark/test-tier3-syntax.sh',
  'tests/benchmark/test-tier4.sh',
  'tests/docs/test-glossary.sh',
  'tests/docs/test-manual-v2.sh',
  'tests/init/test-commands-init.sh',
  'tests/init/test-contract-tier-order.sh',
  'tests/init/test-phase-recommend.sh',
  'tests/init/test-readme-vault-first.sh',
  'tests/init/test-setup-beginner-wizard.sh',
  'tests/init/test-skill-init.sh',
  'tests/push/test-classify-push-diff.sh',
  'tests/router/test-route-model.sh',
  'tests/test-install-vault-search.sh',
  'tests/test-km-version.sh',
]);

function usage() {
  console.log('Usage: node scripts/run-shell-tests.mjs [--list]');
  console.log('Runs the explicit hermetic/fixture shell-test allowlist.');
}

const arg = process.argv[2];
if (arg === '--help' || arg === '-h') {
  usage();
  process.exit(0);
}
if (arg === '--list') {
  for (const test of SAFE_SHELL_TESTS) console.log(test);
  process.exit(0);
}
if (arg !== undefined) {
  console.error(`Unknown option: ${arg}`);
  usage();
  process.exit(2);
}

const missing = SAFE_SHELL_TESTS.filter((test) => !existsSync(resolve(ROOT, test)));
if (missing.length) {
  console.error(`Missing allowlisted shell test(s): ${missing.join(', ')}`);
  process.exit(2);
}

let passed = 0;
let failed = 0;
for (const test of SAFE_SHELL_TESTS) {
  console.log(`\n== ${test} ==`);
  const result = spawnSync('bash', [test], {
    cwd: ROOT,
    stdio: 'inherit',
  });
  if (result.error || result.status !== 0) {
    failed += 1;
    const detail = result.error ? ` (${result.error.message})` : ` (exit ${result.status})`;
    console.error(`FAIL ${test}${detail}`);
  } else {
    passed += 1;
  }
}

console.log(`\nShell test summary: ${passed} passed, ${failed} failed (allowlist=${SAFE_SHELL_TESTS.length})`);
process.exit(failed === 0 ? 0 : 1);
