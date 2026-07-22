#!/usr/bin/env bash
# discord-slash-cmd.sh — UserPromptSubmit hook
#
# 사용자 프롬프트 첫 줄이 `/cmdname` 으로 시작하면 Skill 도구 호출 강제 system-reminder 주입.
#
# 사용 (~/.claude/settings.json):
#   "hooks": {
#     "UserPromptSubmit": [
#       {
#         "matcher": "",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "bash ~/.claude/plugins/thiscode/hooks/discord-slash-cmd.sh",
#             "timeout": 5
#           }
#         ]
#       }
#     ]
#   }
#
# 입력: stdin JSON (Claude Code hook protocol) — {"prompt": "...", ...}
# 출력: 매칭 시 stdout JSON {"hookSpecificOutput":{...}}, 미매칭 시 출력 없음

set -uo pipefail

INPUT=$(cat)

# Windows(Git Bash): python3 이름 부재/스토어 스텁 대응 — python3 → python 폴백
_PY=""
for _c in python3 python; do
  _p="$(command -v "$_c" 2>/dev/null || true)"
  case "$_p" in ''|*WindowsApps*) continue;; esac
  _PY="$_p"; break
done
[ -n "$_PY" ] || exit 0   # 인코더 없으면 fail-open (매칭 포기, 세션 방해 X)

PROMPT=$(echo "$INPUT" | "$_PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get("prompt", ""), end="")
except Exception:
    print("", end="")
' 2>/dev/null)

if [ -z "$PROMPT" ]; then
  exit 0
fi

# 첫 비어있지 않은 줄
FIRST_LINE=$(echo "$PROMPT" | awk 'NF {print; exit}')

# /영문...영숫자-_: 패턴
if echo "$FIRST_LINE" | grep -qE '^[[:space:]]*/[a-zA-Z][a-zA-Z0-9_:-]*'; then
  CMD=$(echo "$FIRST_LINE" | grep -oE '^[[:space:]]*/[a-zA-Z][a-zA-Z0-9_:-]*' | sed 's|^[[:space:]]*/||')

  REMINDER="<system-reminder>
SLASH COMMAND DETECTED: 사용자 프롬프트 첫 줄이 \`/${CMD}\` 로 시작합니다.

이는 슬래시 커맨드 호출 패턴 (Discord / CLI 공통). 준수:
1. VERY FIRST action 으로 Skill 도구를 skill=\"${CMD}\" 인자로 호출
2. 호출 전 설명·확인·프리앰블 일체 금지
3. 커맨드 이름을 다른 스킬로 재해석 X — 정확히 \"${CMD}\" 로 호출
4. 해당 스킬이 available-skills 목록에 없으면 \"Unknown skill: /${CMD}\" 로 짧게 회신
5. 인자 (첫 줄 나머지 + 이후 줄) 는 Skill 의 args 에 전달

이 규율은 다른 응답 패턴보다 우선.
</system-reminder>"

  export REMINDER
  "$_PY" -c '
import json, os
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": os.environ["REMINDER"]
    }
}))
'
fi

exit 0
