#!/bin/bash
# sessionstart-compact-reread.sh — SessionStart hook, matcher="compact".
#
# Fires immediately after a compaction (source=compact). It reads the sidecar
# left by precompact-sot-flush.sh and injects a reminder to re-read the live
# SoT files (rules INDEX, active meeting state, session-edited files) plus the
# bot identity — so the post-compact session grounds on live files, not just
# the compaction summary (which can carry stale facts).
#
# Contract: SessionStart can inject via
#   {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":TEXT}}
# Only acts when source==compact. Consume-once: deletes the sidecar after
# injecting. Cleans orphan sidecars older than 7 days. fail-open, exit 0.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/hookkit.sh"
hk_failopen
hk_read_input

SOURCE="$(hk_json '.source // empty')"
[ "$SOURCE" = "compact" ] || exit 0          # only the post-compact start

SESSION="$(hk_json '.session_id')"
[ -n "$SESSION" ] || exit 0
SAFE="$(printf '%s' "$SESSION" | tr -c 'A-Za-z0-9_-' '_')"
STATE_DIR="${MEETING_WATCHDOG_STATE_DIR:-$HOME/.claude-state}"
SIDECAR="$STATE_DIR/precompact-sot-$SAFE.json"
BOT="$(hk_bot)"

command -v python3 >/dev/null 2>&1 || exit 0
OUT="$(SIDECAR="$SIDECAR" STATE_DIR="$STATE_DIR" BOT="$BOT" python3 - <<'PY' 2>/dev/null || true
import os, json, glob, time
side = os.environ["SIDECAR"]; bot = os.environ.get("BOT", "")
state = os.environ["STATE_DIR"]

# orphan cleanup: sidecars older than 7 days
now = time.time()
for f in glob.glob(os.path.join(state, "precompact-sot-*.json")):
    try:
        if now - os.path.getmtime(f) > 7 * 86400:
            os.remove(f)
    except OSError:
        pass

try:
    d = json.load(open(side, encoding="utf-8"))
except Exception:
    raise SystemExit(0)                       # no sidecar → nothing to inject

paths = (d.get("sot_paths") or [])[:12]
threads = d.get("meeting_threads") or []
ident = bot or d.get("bot") or ""
lines = ["=== compact 직후 SoT 재독 (compaction 요약만 신뢰 ❌) ==="]
if ident:
    lines.append(f"- 정체성: 너는 [{ident}] — 압축 요약이 정체성을 흐리면 soul.md/WD 메타로 복귀.")
lines.append("- rules INDEX 재적재 후 현 상황 트리거 매칭 규칙 재확인.")
if threads:
    lines.append(f"- 활성 회의 {', '.join(threads)} — 02-progress 재독 후 행동.")
if paths:
    lines.append("- 아래 SoT 파일을 다시 읽고 grounding (압축 요약 위에 사실 쌓지 말 것):")
    for p in paths:
        lines.append(f"    {p}")
text = "\n".join(lines)

# consume-once
try:
    os.remove(side)
except OSError:
    pass

print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": text,
}}, ensure_ascii=False))
PY
)"
[ -n "$OUT" ] && printf '%s' "$OUT"
exit 0
