// tests/init/i18n.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { msg, MESSAGES } from '../../scripts/lib/i18n.mjs';

test('plain is the default register', () => {
  assert.equal(msg('wsl_recommend_reason'), MESSAGES.wsl_recommend_reason.plain);
});
test('dev register selectable', () => {
  assert.equal(msg('wsl_recommend_reason', 'dev'), MESSAGES.wsl_recommend_reason.dev);
});
test('every key has both registers, non-empty', () => {
  for (const [k, v] of Object.entries(MESSAGES)) {
    assert.ok(v.plain && v.plain.length, `${k}.plain missing`);
    assert.ok(v.dev && v.dev.length, `${k}.dev missing`);
  }
});
test('unknown key throws (no silent empty UX)', () => {
  assert.throws(() => msg('no_such_key'));
});
