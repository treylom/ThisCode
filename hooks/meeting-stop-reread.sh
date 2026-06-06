#!/usr/bin/env bash
# meeting-stop-reread.sh — Stop hook for active meeting reread (fail-open)
#
# Safety invariant:
# - Emits {"decision":"block","reason":...} ONLY when this is a bot session, an
#   active meeting file exists, and the hook is not already recursive.
#   Stop has NO hookSpecificOutput variant — that shape fails Claude Code's
#   hook-output schema; decision:block+reason is the only valid block+inject.
# - Everything else allows stop silently: empty stdout + exit 0.
# - Paths derive from env/BOT_WD/PWD. No maintainer-machine hardcoding.
# - A non-Claude-Code Stop runner must map this contract itself (fail-open).
set -uo pipefail

input="$(cat 2>/dev/null || true)"

command -v python3 >/dev/null 2>&1 || exit 0

export HOOK_INPUT="$input"
python3 - <<'PY'
import json, os, pathlib, sys

try:
    payload = json.loads(os.environ.get("HOOK_INPUT") or "{}")
except Exception:
    payload = {}

event = payload.get("hook_event_name") or payload.get("hookEventName")
if event and event != "Stop":
    sys.exit(0)
if payload.get("stop_hook_active") is True:
    sys.exit(0)

bot_session = bool(os.environ.get("DISCORD_STATE_DIR") or os.environ.get("BOT_WD"))
if not bot_session:
    sys.exit(0)

meeting_dir = os.environ.get("MEETING_PROTOCOL_DIR")
if not meeting_dir and os.environ.get("BOT_WD"):
    meeting_dir = os.path.join(os.environ["BOT_WD"], "meetings")
if not meeting_dir:
    meeting_dir = os.path.join(os.getcwd(), "meetings")

active = pathlib.Path(os.environ.get("MEETING_ACTIVE_FILE") or os.path.join(meeting_dir, "ACTIVE.md"))
if not active.is_file():
    sys.exit(0)

try:
    body = active.read_text(encoding="utf-8")
except Exception:
    body = ""

# blocked_on done-waiting carve-out (meeting-protocol.md §3): meeting 이 게이트
# 대기(blocked/paused)면 참여봇 침묵 = done-waiting 정상 → 매 stop 재독 강제는
# 무익 cycling 만 유발한다. ACTIVE.md 에 값 있는 'blocked_on:' 마커가 있으면
# reread 강제 skip(=stop 허용). 마커 부재 → 기존 동작 유지(하위호환).
import re as _re
_m = _re.search(r"(?mi)^\s*blocked_on\s*:\s*(.+)$", body)
if _m:
    _v = _m.group(1).strip().split("#", 1)[0].strip().lower()
    if _v and _v not in ("null", "none", "-", "[]"):
        sys.exit(0)

context = (
    f"=== active meeting reread required ({active}) ===\n\n"
    f"{body}\n\n"
    "Before stopping, reread the active meeting state, update progress if needed, "
    "and report blocked/partial/completion status through the channel."
)
# Stop event: only decision:block + reason is valid (no hookSpecificOutput).
print(json.dumps({
    "decision": "block",
    "reason": context,
}, ensure_ascii=False))
PY
