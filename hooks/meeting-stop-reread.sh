#!/usr/bin/env bash
# meeting-stop-reread.sh — Stop hook for active meeting reread (fail-open)
#
# Safety invariant:
# - continue:true only when this is a bot session, an active meeting file exists,
#   and the hook is not already recursive.
# - Everything else allows stop silently.
# - Paths derive from env/BOT_WD/PWD. No maintainer-machine hardcoding.
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

context = (
    f"=== active meeting reread required ({active}) ===\n\n"
    f"{body}\n\n"
    "Before stopping, reread the active meeting state, update progress if needed, "
    "and report blocked/partial/completion status through the channel."
)
print(json.dumps({
    "continue": True,
    "reason": "active meeting reread required before Stop",
    "hookSpecificOutput": {
        "hookEventName": "Stop",
        "additionalContext": context,
    },
}, ensure_ascii=False))
PY
