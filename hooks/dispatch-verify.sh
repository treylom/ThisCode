#!/bin/bash
# dispatch-verify.sh — Stop hook (B3, orchestrator 한정): 다른 봇에게 작업을 dispatch
#   (봇 @mention 이 담긴 Discord reply)한 뒤 tmux capture-pane 으로 실행 진입을 실측 검증하지
#   않고 종료하려 하면 1턴 연장 + 리마인드. 근거: meeting-protocol §2 / orchestration §2 (ack≠execution).
# orchestrator 봇 세션에서만 동작 (ORCHESTRATOR_BOT env 로 봇 이름 지정, default: orchestrator).
# fail-open + 재귀가드 + 자동화 skip.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/hookkit.sh"
hk_failopen
hk_read_input
hk_stop_active && hk_allow_stop
[ "$(hk_bot)" = "${ORCHESTRATOR_BOT:-orchestrator}" ] || hk_allow_stop
hk_is_automation && hk_allow_stop
TRANSCRIPT="$(hk_transcript)"
[ -n "$TRANSCRIPT" ] || hk_allow_stop
[ -f "$TRANSCRIPT" ] || hk_allow_stop
command -v python3 >/dev/null 2>&1 || hk_allow_stop

RESULT="$(TR="$TRANSCRIPT" python3 2>/dev/null <<'PY'
import json, os, re
USER_ID = os.environ.get("OWNER_USER_ID", "")          # 운영자(사람) user id — 봇 dispatch 아님(제외)
MENTION = re.compile(r"<@!?(\d{15,20})>")
path = os.environ["TR"]
try:
    lines = open(path, encoding="utf-8").read().splitlines()
except OSError:
    raise SystemExit(0)
last_inbound = -1
dispatched = False
verified = True
idx = 0
for ln in lines:
    ln = ln.strip()
    if not ln: continue
    try: m = json.loads(ln)
    except Exception: continue
    if m.get("type") not in ("user", "assistant"): continue
    msg = m.get("message", {})
    if not isinstance(msg, dict): continue
    role = msg.get("role"); content = msg.get("content")
    if role == "user":
        blob = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        if "<channel source=" in blob:
            last_inbound = idx; dispatched = False; verified = True
    elif role == "assistant" and isinstance(content, list):
        for b in content:
            if not isinstance(b, dict) or b.get("type") != "tool_use": continue
            name = b.get("name", "") or ""
            inp = b.get("input", {}) or {}
            if "discord" in name and ("reply" in name or "message" in name):
                txt = str(inp.get("text", ""))
                ids = [i for i in MENTION.findall(txt) if i != USER_ID]
                if ids:
                    dispatched = True; verified = False
            elif name == "Bash":
                if "capture-pane" in str(inp.get("command", "")) and dispatched:
                    verified = True
    idx += 1
print("VIOLATION" if (dispatched and not verified) else "OK")
PY
)" || true

if [ "$RESULT" = "VIOLATION" ]; then
  hk_log "B3 dispatch-verify: 봇 dispatch 후 tmux 미검증 종료 → block"
  hk_block_stop "[dispatch 검증 · meeting-protocol §2] 다른 봇에게 작업을 dispatch(멘션)한 뒤 tmux capture-pane 으로 실행 진입을 실측 검증하지 않고 종료하려 합니다. ack ≠ execution — 특히 Codex bridge 봇은 ack 후 idle 가능. 대상 봇이 실제 작업에 들어갔는지 tmux 로 확인하세요. 단순 알림/broadcast 였다면 이 메시지를 무시해도 됩니다."
fi
hk_allow_stop
