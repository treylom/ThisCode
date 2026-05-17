#!/usr/bin/env node
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

function collectTests(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectTests(path));
    } else if (entry.isFile() && entry.name.endsWith('.test.mjs')) {
      out.push(path);
    }
  }
  return out.sort();
}

const tests = collectTests('tests');
if (!tests.length) {
  console.error('No tests found under tests/**/*.test.mjs');
  process.exit(1);
}

const result = spawnSync(process.execPath, ['--test', ...tests], { stdio: 'inherit' });
process.exit(result.status ?? 1);
