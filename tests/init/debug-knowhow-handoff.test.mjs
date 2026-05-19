// WSL repo-handoff debug log (2026-05-18) findings E + J-2 must be captured
// in the operational debug-knowhow doc and the bot-creation wizard, since
// they can't be fixed in our repo (server.ts is the external official plugin)
// or are operational (each bot needs its own OAuth invite). RED → GREEN.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8');
const debugDoc = read('../../docs/08-debug-노하우.md');
const createBot = read('../../commands/create-bot.md');
const start = read('../../commands/start.md');

test('J-2: debug doc documents the discord server.ts msg.author.bot blanket-drop', () => {
  assert.match(
    debugDoc,
    /msg\.author\.bot/,
    'must name the exact gate (msg.author.bot) so it is greppable',
  );
  assert.match(
    debugDoc,
    /server\.ts/,
    'must point at server.ts (the external official discord plugin)',
  );
  // re-apply note: it lives in marketplaces/ → overwritten on plugin update
  assert.match(
    debugDoc,
    /재적용|plugin update|덮어쓰|overwrit/i,
    'must carry the re-apply-after-plugin-update note (J-1 realized)',
  );
});

test('J-3: debug doc documents per-bot OAuth invite + no-response diagnostics', () => {
  assert.match(
    debugDoc,
    /봇\s*(앱\s*)?(마다|별)\s*.*초대|each bot.*invite|별도 (서버 )?초대/i,
    'must state each bot app needs its own separate server invite',
  );
  assert.match(
    debugDoc,
    /users\/@me\/guilds|\/users\/@me/,
    'must include the no-response diagnostic API checks',
  );
});

test('E: bot-creation wizard flags the multi-bot separate-invite trap', () => {
  for (const [name, md] of [['create-bot.md', createBot], ['start.md', start]]) {
    assert.match(
      md,
      /봇\s*(앱\s*)?(마다|별).*초대|별도.*초대|각.*봇.*초대/,
      `${name} must flag that each bot app needs its own server invite`,
    );
  }
});

// codex parity (J-2 cross-ref in ThisCodex SKILL.md) is locked by ThisCodex's
// own tests/init/repo-handoff.test.mjs — a ThisCode test must not depend on a
// sibling repo's filesystem layout (porting-infra §2: each repo self-tests).
