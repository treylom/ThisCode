// Thin wrapper: runs the Python S2 solo-ledger fixture harness inside the
// node --test suite. The harness itself enforces FAIL 0 + assertion-count +
// decoy-count (positive/negative) before it will exit 0 — see run-fixtures.py.
import test from 'node:test';
import assert from 'node:assert';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

test('S2 solo-ledger fixtures ①~④ (EIO/restart · race · CLEAR · lock/orphan)', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const r = spawnSync('python3', [join(here, 'run-fixtures.py')],
    { encoding: 'utf8', timeout: 120_000 });
  assert.equal(r.status, 0, `harness exit ${r.status}\n${r.stdout}\n${r.stderr}`);
  assert.match(r.stdout, /ALL GREEN \(FAIL 0 \+ 계수 일치 \+ exit 0\)/);
});
