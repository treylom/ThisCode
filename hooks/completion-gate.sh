#!/bin/bash
# completion-gate.sh — Stop hook (B4): 운영자(owner)에게 "완료/마감"을 선언하는 Discord 메시지를
#   보냈는데 지정 completion thread(COMPLETION_THREAD_ID env) 선보고가 이번 대화에 없으면
#   1턴 연장 + 리마인드. 근거: autonomy.md §2 / discord-comms §4. 반복 운영 루프 봇 제외.
# fail-open: 재귀/자동화/transcript 부재/파싱실패/python 부재 → 정상 종료 허용.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/hookkit.sh"
hk_failopen
hk_read_input
hk_stop_active && hk_allow_stop
hk_is_automation && hk_allow_stop
TRANSCRIPT="$(hk_transcript)"
[ -n "$TRANSCRIPT" ] || hk_allow_stop
[ -f "$TRANSCRIPT" ] || hk_allow_stop
command -v python3 >/dev/null 2>&1 || hk_allow_stop

RESULT="$(TR="$TRANSCRIPT" python3 2>/dev/null <<'PY'
import json, os
COMPLETION_THREAD = os.environ.get("COMPLETION_THREAD_ID", "")
if not COMPLETION_THREAD:
    print("OK"); raise SystemExit(0)
WORDS = ("완료", "마감", "끝났", "납품", "완성했")
path = os.environ["TR"]
try:
    lines = open(path, encoding="utf-8").read().splitlines()
except OSError:
    raise SystemExit(0)
last_inbound = -1
reported = False     # completion thread 선보고가 마지막 인바운드 이후 존재?
declared = False     # 완료 단어를 담은 일반 Discord reply 가 마지막 인바운드 이후 존재?
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
            last_inbound = idx; reported = False; declared = False
    elif role == "assistant" and isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                name = b.get("name", "") or ""
                if "discord" in name and ("reply" in name or "message" in name):
                    inp = b.get("input", {}) or {}
                    cid = str(inp.get("chat_id", ""))
                    txt = str(inp.get("text", ""))
                    if cid == COMPLETION_THREAD:
                        reported = True
                    elif any(w in txt for w in WORDS):
                        declared = True
    idx += 1
print("VIOLATION" if (declared and not reported) else "OK")
PY
)" || true

if [ "$RESULT" = "VIOLATION" ]; then
  hk_log "B4 completion-gate: 완료 선언 + completion thread 미보고 → block"
  hk_block_stop "[완료 게이트 · autonomy §2] 운영자에게 '완료/마감'을 선언하는 Discord 메시지 직전인데, 지정된 completion thread 선보고 기록이 이번 대화에 없습니다. 특정 업무(제안서·납품·마일스톤·의뢰 산출·공개레포 변경) 완료라면 먼저 그 completion thread 에 '[작업명] 완료. 산출: <경로>' 를 보내세요. 반복 운영 루프거나 단순 진행 보고면 이 메시지를 무시하고 정상 종료해도 됩니다."
fi
hk_allow_stop
