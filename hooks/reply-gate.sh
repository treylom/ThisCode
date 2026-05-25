#!/bin/bash
# reply-gate.sh — Stop hook (B2, soft→hard): 외부 채널(Discord) 사용자 인바운드에
#   reply 도구로 응답하지 않은 채 종료하려 하면 1턴 연장 + 발송 리마인드 주입.
# 근거: discord-comms.md §1 — 사용자는 터미널이 아니라 Discord 를 본다. 04-synthesis B2 (전봇 회귀 ★★).
# fail-open: transcript 부재/파싱실패/python 부재/재귀/비-Discord turn → 정상 종료 허용.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/hookkit.sh"
hk_failopen
hk_read_input
hk_stop_active && hk_allow_stop
TRANSCRIPT="$(hk_transcript)"
[ -n "$TRANSCRIPT" ] || hk_allow_stop
[ -f "$TRANSCRIPT" ] || hk_allow_stop
command -v python3 >/dev/null 2>&1 || hk_allow_stop

RESULT="$(TR="$TRANSCRIPT" python3 2>/dev/null <<'PY'
import json, os
path = os.environ["TR"]
try:
    lines = open(path, encoding="utf-8").read().splitlines()
except OSError:
    raise SystemExit(0)
last_inbound = -1
reply_after = True   # 인바운드가 하나도 없으면 위반 아님(True 로 시작)
idx = 0
for ln in lines:
    ln = ln.strip()
    if not ln:
        continue
    try:
        m = json.loads(ln)
    except Exception:
        continue
    if m.get("type") not in ("user", "assistant"):
        continue
    msg = m.get("message", {})
    if not isinstance(msg, dict):
        continue
    role = msg.get("role")
    content = msg.get("content")
    if role == "user":
        try:
            blob = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        except Exception:
            blob = ""
        if "<channel source=" in blob:        # 외부 채널 인바운드 (tool_result 등은 미해당)
            last_inbound = idx
            reply_after = False
    elif role == "assistant":
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    name = b.get("name", "") or ""
                    if "discord" in name and "reply" in name and last_inbound >= 0:
                        reply_after = True
    idx += 1
print("VIOLATION" if (last_inbound >= 0 and not reply_after) else "OK")
PY
)" || true

if [ "$RESULT" = "VIOLATION" ]; then
  hk_log "B2 reply-gate: Discord 인바운드 미응답 종료 시도 → block"
  hk_block_stop "[reply 게이트 · discord-comms §1] 외부 채널(Discord) 사용자 인바운드에 reply 도구(mcp__plugin_discord_discord__reply)로 응답하지 않은 채 종료하려 합니다. 사용자는 터미널이 아니라 Discord 를 보므로 터미널 출력만으로는 도달하지 않습니다. 응답이 필요하면 reply 로 발송하세요. 이미 다른 방식(REST 등)으로 보냈거나 응답이 불필요하면 이 메시지를 무시하고 정상 종료해도 됩니다."
fi
hk_allow_stop
