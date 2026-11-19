#!/usr/bin/env bash
# stop-pending-task-check.sh — Claude Code Stop hook
# thiscode v2.3 — session 종료 시 pending task 확인 + 사용자 알림
#
# 본 hook 의 의도: 자율 cycle 안 미완 task 남기지 않게 사용자 visibility 보장.
# 2026-05-13 spec.
#
# 설치 방법 (사용자 ~/.claude/hooks/ 안):
#   1. 본 file cp ~/.claude/hooks/stop-pending-task-check.sh
#   2. chmod +x ~/.claude/hooks/stop-pending-task-check.sh
#   3. ~/.claude/settings.json 안 hooks 등록:
#      {
#        "hooks": {
#          "Stop": [{
#            "matcher": "",
#            "hooks": [{"type": "command", "command": "~/.claude/hooks/stop-pending-task-check.sh"}]
#          }]
#        }
#      }
#
# 본 hook 의 동작:
# - stdin JSON 안 session info parse
# - vault `docs/superpowers/plans/*.md` 안 모든 `- [ ]` (pending checkbox) count
# - count > 0 시 stderr 안 알림 + exit 2 (Claude Code 안 deny session end + 사용자 visibility)
# - count == 0 시 exit 0 (silent)
set -euo pipefail

# v2.3.2: stdin JSON parse + Stop event filter + recursive bypass + cwd fallback
# Session info (Claude Code 안 stdin 으로 hook 호출 시 JSON 전달)
input="$(cat 2>/dev/null || true)"

# JSON parse (jq 있을 때만 — 없으면 graceful skip 안 단순 trigger)
if command -v jq >/dev/null 2>&1 && [[ -n "$input" ]]; then
  event="$(jq -r '.hook_event_name // empty' <<<"$input" 2>/dev/null || true)"
  active="$(jq -r '.stop_hook_active // false' <<<"$input" 2>/dev/null || true)"
  cwd="$(jq -r '.cwd // empty' <<<"$input" 2>/dev/null || true)"

  # Stop event 가 아니거나 recursive Stop hook 활성 시 silent skip
  if [[ -n "$event" && "$event" != "Stop" ]]; then
    exit 0
  fi
  if [[ "$active" == "true" ]]; then
    exit 0
  fi
else
  cwd=""
fi

# vault path (env override > stdin cwd > default)
VAULT="${CLAUDE_DISCODE_VAULT:-${VAULT:-${cwd:-${HOME}/vault}}}"
PLAN_DIR="${VAULT}/docs/superpowers/plans"

if [[ ! -d "$PLAN_DIR" ]]; then
  # vault / plan dir 없음 — silent exit
  exit 0
fi

# 모든 plan doc 안 pending checkbox count
pending=0
declare -a pending_files=()
while IFS= read -r -d '' plan; do
  # v2.3.2: regex 안 indented + `* [ ]` task 도 catch
  n=$(grep -Ec '^[[:space:]]*[-*][[:space:]]+\[[[:space:]]\]' "$plan" 2>/dev/null || true)
  if [[ "${n:-0}" -gt 0 ]]; then
    pending=$(( pending + n ))
    pending_files+=("$(basename "$plan"): $n")
  fi
done < <(find "$PLAN_DIR" -maxdepth 1 -name "*.md" -print0 2>/dev/null)

if [[ "$pending" -eq 0 ]]; then
  # 미완 task zero — silent exit
  exit 0
fi

# 미완 task 발견 — stderr 알림 + exit 2 (deny session end + Claude Code 안 가시)
cat >&2 <<EOF

⚠️  thiscode Stop hook — pending task ${pending}건 감지

미완 plan doc:
$(printf '  - %s\n' "${pending_files[@]}")

본 hook 의 의도: 자율 cycle 안 미완 task 남기지 않게 사용자 visibility 보장.

본 session 종료 시:
  → Claude Code 안 TaskList 호출 → status=pending task 확인
  → 또는 plan doc 안 \`- [ ]\` checkbox 진행
  → 모든 task 완료 후 본 hook silent exit

명시적 session 종료 의도 시: 본 hook 비활성 (~/.claude/settings.json 안 Stop hook 제거).
EOF
exit 2
