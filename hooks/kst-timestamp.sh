#!/bin/bash
# kst-timestamp.sh — Stop hook (B6): 사용자에게 보내는 Discord reply 텍스트에 UTC 타임스탬프가
#   들어가면 1턴 연장 + KST 변환 리마인드. 근거: meeting-protocol §4 (전 봇 시각 표기 = KST 고정).
#   사용자-대면 reply 텍스트만 검사(내부 도구 출력·인바운드 ts 미검사) → false-positive 최소.
# fail-open + 재귀가드 + 자동화 skip. 04-synthesis B6.
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
import json, os, re
ISO_Z = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?Z")
UTC_T = re.compile(r"\d{1,2}:\d{2}\s*UTC\b")
path = os.environ["TR"]
try:
    lines = open(path, encoding="utf-8").read().splitlines()
except OSError:
    raise SystemExit(0)
last_inbound = -1
violation = False
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
            last_inbound = idx; violation = False
    elif role == "assistant" and isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                name = b.get("name", "") or ""
                if "discord" in name and ("reply" in name or "message" in name):
                    txt = str((b.get("input", {}) or {}).get("text", ""))
                    if ISO_Z.search(txt) or UTC_T.search(txt):
                        violation = True
    idx += 1
print("VIOLATION" if violation else "OK")
PY
)" || true

if [ "$RESULT" = "VIOLATION" ]; then
  hk_log "B6 kst: Discord reply 에 UTC 타임스탬프 → block"
  hk_block_stop "[KST 강제 · meeting-protocol §4] 사용자에게 보내는 Discord 메시지에 UTC 타임스탬프(…Z 또는 'NN:NN UTC')가 들어 있습니다. 전 봇 시각 표기는 KST(UTC+9) 고정입니다 — KST 로 환산해 다시 보내세요. 로그 원문 인용 등 의도적 UTC 표기였다면 이 메시지를 무시해도 됩니다."
fi
hk_allow_stop
