import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('../', import.meta.url));
const posixOnlySkip = process.platform === 'win32'
  ? 'POSIX shell fixtures; exercised by macOS and Ubuntu jobs'
  : false;

for (const installer of ['ripgrep', 'superpowers', 'dense-embedding']) {
  for (const mode of ['--help', '-h', '--invalid', '--check']) {
    test(`${installer} ${mode} does not write setup logs`, { skip: posixOnlySkip }, (t) => {
      const fixture = mkdtempSync(join(tmpdir(), 'thiscode-readonly-'));
      t.after(() => rmSync(fixture, { recursive: true, force: true }));
      const fixtureBin = join(fixture, 'bin');
      mkdirSync(fixtureBin);
      const marker = join(fixture, 'rg-called');
      writeFileSync(join(fixtureBin, 'rg'), '#!/bin/sh\nprintf called > "$RG_TEST_MARKER"\nprintf "ripgrep fixture\\n"\n', { mode: 0o755 });
      // Keep checks local: never invoke the host plugin manager.
      writeFileSync(join(fixtureBin, 'claude'), '#!/bin/sh\nexit 1\n', { mode: 0o755 });
      const result = spawnSync('/bin/bash', [join(root, 'scripts', `install-${installer}.sh`), mode], {
        encoding: 'utf8',
        env: { ...process.env, HOME: fixture, PATH: `${fixtureBin}:/usr/bin:/bin`,
          CLAUDE_DISCODE_VENV: join(fixture, 'missing-venv'), RG_TEST_MARKER: marker },
      });
      assert.ifError(result.error);
      const output = result.stdout + result.stderr;
      const expected = mode === '--invalid' ? 2 : mode === '--check' && installer !== 'ripgrep' ? 1 : 0;
      assert.equal(result.status, expected, output);
      if (mode === '--help' || mode === '-h') assert.match(output, /Usage:/);
      if (mode !== '--check') assert.equal(existsSync(marker), false, 'argument parsing must precede detection');
      assert.equal(existsSync(join(fixture, '.thiscode-setup.log')), false, 'read-only mode created a setup log');
    });
  }
}
