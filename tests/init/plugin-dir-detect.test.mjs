// Finding A (WSL repo-handoff debug log 2026-05-18 §9-부록 A): PLUGIN_DIR
// auto-detect only covered `marketplaces/thiscode-marketplace` + `~/code/thiscode`,
// missing the manual clone (`~/.claude/plugins/thiscode`) and the canonical
// install cache (`~/.claude/plugins/cache/local/thiscode`). Same brittle
// pattern recurs in self-update.md, and create-bot.md consumes $PLUGIN_DIR
// without ever assigning it. RED before the fix, GREEN after.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8');
const installHooks = read('../../commands/install-hooks.md');
const selfUpdate = read('../../commands/self-update.md');
const createBot = read('../../commands/create-bot.md');

test('A: install-hooks.md PLUGIN_DIR detect covers manual clone + install cache', () => {
  assert.match(
    installHooks,
    /plugins\/thiscode\b/,
    'must probe the manual-clone location ~/.claude/plugins/thiscode',
  );
  assert.match(
    installHooks,
    /plugins\/cache\/local\/thiscode/,
    'must probe the canonical install cache ~/.claude/plugins/cache/local/thiscode',
  );
});

test('A: install-hooks.md drops the brittle bare `[ -d $PLUGIN_DIR/hooks ]` fallback', () => {
  // The old single fallback `[ -d "$PLUGIN_DIR/hooks" ] || PLUGIN_DIR=...`
  // only ever tried 2 locations. The fix replaces it with an ordered probe.
  assert.doesNotMatch(
    installHooks,
    /\[ -d "\$PLUGIN_DIR\/hooks" \] \|\| PLUGIN_DIR=/,
    'the 2-candidate brittle fallback must be replaced by an ordered probe',
  );
});

test('A: self-update.md candidate list includes manual clone + cache', () => {
  assert.match(selfUpdate, /plugins\/thiscode\b/, 'self-update must consider ~/.claude/plugins/thiscode');
  assert.match(
    selfUpdate,
    /plugins\/cache\/local\/thiscode/,
    'self-update must consider ~/.claude/plugins/cache/local/thiscode',
  );
});

test('A: create-bot.md assigns PLUGIN_DIR before consuming $PLUGIN_DIR/templates', () => {
  // The bug: create-bot.md used "$PLUGIN_DIR/templates/..." with no assignment
  // anywhere. The `${PLUGIN_DIR:-}` guard is a safe reference, not a consume —
  // assert the assignment precedes the actual templates consume.
  // Real consume anchor = `TEMPLATE="$PLUGIN_DIR/templates/...` (builds the
  // path actually copied). `[ -d "$PLUGIN_DIR/templates" ]` in the detect
  // guard is a safe probe, not the consume.
  const assignIdx = createBot.search(/PLUGIN_DIR="\$_cand"/);
  const consumeIdx = createBot.search(/TEMPLATE="\$PLUGIN_DIR\/templates/);
  assert.ok(assignIdx !== -1, 'create-bot.md must detect+assign PLUGIN_DIR (it never did)');
  assert.ok(consumeIdx !== -1, 'create-bot.md still builds TEMPLATE from $PLUGIN_DIR/templates');
  assert.ok(
    assignIdx < consumeIdx,
    'PLUGIN_DIR detection must run before TEMPLATE="$PLUGIN_DIR/templates"',
  );
});
