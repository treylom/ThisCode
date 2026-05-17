// scripts/lib/manifest-runner.mjs — deterministic ordered runner (spec §1/C1, §3.2 mirror).
// D2: condition DSL is LOCKED identical to ThisCodex flow-runner.mjs evaluateWhen (spec §1/§7
// "shared engine semantics") — supports 'always' | dotted-path | quoted-string | boolean, e.g.
// "os == 'win'", "mode == 'apply'", "answers.alias_consent == 'yes'", "tools.tmux == false".
// No eval; regex + safe path read only.
function readPath(obj, path) {
  return path.split('.').reduce((acc, key) => (acc == null ? undefined : acc[key]), obj);
}

function parseValue(raw) {
  const v = raw.trim();
  if ((v.startsWith("'") && v.endsWith("'")) || (v.startsWith('"') && v.endsWith('"'))) return v.slice(1, -1);
  if (v === 'false') return false;
  if (v === 'true') return true;
  return v;
}

export function evalWhen(when, ctx) {
  if (!when || when === 'always') return true;
  const m = when.match(/^([a-zA-Z0-9_.]+)\s*==\s*(.+)$/);
  if (!m) return false;
  return readPath(ctx || {}, m[1]) === parseValue(m[2]);
}

export function runManifest(steps, opts = {}) {
  const ctx = opts.ctx || {};
  const actions = opts.actions || {};
  const verifiers = opts.verifiers || {};
  const emit = opts.emit || (() => {});
  const ordered = steps.slice().sort((a, b) => a.order - b.order);
  for (const s of ordered) {
    if (!evalWhen(s.when, ctx)) continue;            // skip out-of-scope, no hang
    emit(s.reason);                                   // friendly: show WHY before doing
    const act = actions[s.action];
    if (act) act(s, ctx);
    const v = verifiers[s.verify && s.verify.type];
    const pass = v ? v(s, ctx) : true;
    if (!pass) {
      return { ok: false, failed: s.id, next_command: (s.on_fail && s.on_fail.next_command) || null };
    }
  }
  return { ok: true };
}
