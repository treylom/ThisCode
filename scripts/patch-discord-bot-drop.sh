#!/usr/bin/env bash
# patch-discord-bot-drop.sh — J-2 permanent re-apply layer.
#
# The official discord plugin (`…/external_plugins/discord/server.ts`) drops
# every bot-authored message with `if (msg.author.bot) return` BEFORE gate(),
# which breaks multi-bot collaboration. That file lives in `marketplaces/`
# (= outside ThisCode) so a plugin update overwrites any in-place fix
# (J-1 realized). This script idempotently re-applies the 3-guard.
#
# Safety invariants:
#   - fail-OPEN: always `exit 0` (wired into /self-update — must never brick it)
#   - backup `.thiscode-j2.bak-<ts>` before any edit
#   - exact-match only: edits ONLY the precise vulnerable line
#   - idempotent: a marker comment makes re-runs a no-op
#   - upstream changed shape (no vuln line, no marker) → WARN, never blind-edit
#
# Usage: bash patch-discord-bot-drop.sh        (auto-locates the plugin)
#        PATCH_TARGET=<file> bash …            (explicit target — tests)
# Recipe / context: ThisCode docs/08-debug-노하우.md J-2.
set -uo pipefail
MARKER="thiscode-j2-guard"

TARGET="${PATCH_TARGET:-}"
if [ -z "$TARGET" ]; then
  for c in \
    "$HOME/.claude/plugins/marketplaces/claude-plugins-official/external_plugins/discord/server.ts" \
    "$HOME"/.claude/plugins/cache/claude-plugins-official/discord/*/server.ts; do
    if [ -f "$c" ]; then TARGET="$c"; break; fi
  done
fi

if [ -z "${TARGET:-}" ] || [ ! -f "$TARGET" ]; then
  echo "[j2-patch] discord plugin server.ts not found — skip (nothing to patch)"
  exit 0
fi

if grep -q "$MARKER" "$TARGET" 2>/dev/null; then
  echo "[j2-patch] already patched ($MARKER present) — no-op: $TARGET"
  exit 0
fi

if ! grep -Eq '^[[:space:]]*if \(msg\.author\.bot\) return;?[[:space:]]*$' "$TARGET"; then
  echo "[j2-patch] WARN: blanket-drop line not found and no marker — upstream discord plugin may have changed shape. NO edit made; manual review: ThisCode docs/08-debug-노하우.md J-2." >&2
  exit 0
fi

cp "$TARGET" "$TARGET.thiscode-j2.bak-$(date -u +%Y%m%d-%H%M%S)" 2>/dev/null || {
  echo "[j2-patch] WARN: could not write backup; aborting without edit ($TARGET)" >&2
  exit 0
}

MARKER="$MARKER" python3 - "$TARGET" <<'PY'
import os, re, sys
path = sys.argv[1]
marker = os.environ["MARKER"]
src = open(path, encoding="utf-8").read()
pat = re.compile(r'^([ \t]*)if \(msg\.author\.bot\) return;?[ \t]*$', re.M)
def repl(m):
    ind = m.group(1)
    return (
        f"{ind}// {marker}: blanket bot-drop -> 3-guard (ThisCode docs/08-debug-노하우.md J-2)\n"
        f"{ind}if (msg.author.id === client.user?.id) return\n"
        f"{ind}if (msg.webhookId) return\n"
        f"{ind}if (msg.author.bot && !msg.guild) return"
    )
new, n = pat.subn(repl, src, count=1)
if n != 1:
    sys.stderr.write("[j2-patch] internal: replacement count != 1\n")
    sys.exit(3)
# Atomic write: a mid-write crash must never leave server.ts truncated.
# Write a sibling temp file, fsync, then os.replace (atomic on same fs).
import os, tempfile
d = os.path.dirname(path) or "."
fd, tmp = tempfile.mkstemp(prefix=".j2-", dir=d)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(new)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
except Exception:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise
PY
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "[j2-patch] ERROR: patch failed (rc=$rc) — .bak retained, file left as-is" >&2
  exit 0   # fail-open
fi
echo "[j2-patch] patched (3-guard applied, .bak saved): $TARGET"
exit 0
