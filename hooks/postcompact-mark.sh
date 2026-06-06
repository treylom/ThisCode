#!/bin/bash
# postcompact-mark.sh — PostCompact hook (observe-only).
#
# PostCompact fires right after a compaction completes. It CANNOT inject
# context (no hookSpecificOutput), so its only job here is to mark the
# PreCompact sidecar as compacted. The actual SoT re-read reminder is done
# by SessionStart(matcher=compact) — see sessionstart-compact-reread.sh.
#
# Why the chain: a frequent auto-compact (small-context models) swaps the
# live conversation for a summary. If the bot then trusts only the summary
# and skips re-reading the live SoT files, it drifts (stale facts). PreCompact
# stashes "what to re-read" into a sidecar; SessionStart(compact) re-injects it.
#
# fail-open: any error → exit 0 (never blocks). Automation sessions skip.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/hookkit.sh"
hk_failopen
hk_read_input
hk_is_automation && exit 0

SESSION="$(hk_json '.session_id')"
[ -n "$SESSION" ] || exit 0
SAFE="$(printf '%s' "$SESSION" | tr -c 'A-Za-z0-9_-' '_')"
STATE_DIR="${MEETING_WATCHDOG_STATE_DIR:-$HOME/.claude-state}"
SIDECAR="$STATE_DIR/precompact-sot-$SAFE.json"
[ -f "$SIDECAR" ] || exit 0

KST="$(hk_now_kst)"
if command -v python3 >/dev/null 2>&1; then
  SIDECAR="$SIDECAR" KST="$KST" python3 - <<'PY' 2>/dev/null || true
import os, json
p = os.environ["SIDECAR"]
try:
    d = json.load(open(p, encoding="utf-8"))
except Exception:
    raise SystemExit(0)
d["compacted_kst"] = os.environ.get("KST", "")
try:
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
except OSError:
    pass
PY
  hk_log "postcompact mark: $(basename "$SIDECAR")"
fi
exit 0
