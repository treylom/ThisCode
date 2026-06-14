#!/usr/bin/env bash
# regression-self-check.sh — UserPromptSubmit hook
#
# 매 user input 시 4-gate self-check 표 stdout 주입 → attention pool 환기로 회귀 차단.
#
# 사용 (~/.claude/settings.json):
#   "hooks": {
#     "UserPromptSubmit": [
#       {
#         "matcher": "",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "bash ~/.claude/plugins/thiscode/hooks/regression-self-check.sh",
#             "timeout": 3
#           }
#         ]
#       }
#     ]
#   }
#
# 본 hook 은 stdout 으로 직접 출력 (Claude Code 가 system-reminder 로 자동 변환).
# 사용자 자기 환경 customize 시 본 파일 4-gate 표를 자기 회귀 case 로 수정.

cat <<'EOF'
⚠️ Pre-response self-check (회귀 차단):

1. [Discord reply gate] 외부 채널 응답 task 인가?
   → 터미널 출력만 X, mcp__plugin_discord_discord__reply 등 도구 우선

2. [단정 표현 lint] "절대/반드시/금지" 작성 후보 인가?
   → 다른 운영 사례 cross-check 의무

3. [Single-grep trap] vault fact 점검 단일 grep 으로 끝났는가?
   → hub 파일 + 다른 봇 같은 영역 + OCR 인지 다축 cross-check

4. [Skill invoke gate] creative / debugging / verification task 인가?
   → superpowers skill BEFORE response (Red Flag 표 통과)

5. [자동 루프 다양성 게이트] 반복 LLM 변형/최적화 루프가 "수렴/완료" 판정 직전인가?
   → skeleton 다양성(골격 중복률·self-loop 비율) 1회 확인. 골격 정체(단말만
     치환) = attractor 의심 → cross-model / lateral / diverse seeds 주입 후 재판정.
EOF

exit 0
