#!/bin/bash
# hookkit.sh — soft→hard enforcement 훅 공용 라이브러리 (source 전용, 직접 실행 ❌)
#
# 출처: AI_Second_Brain/meetings/2026-05-25-soft-to-hard-rule-enforcement/05-implementation-plan.md
#       maintainer 1차 승인 2026-05-25. 패턴 미러:
#       .claude/scripts/{meeting-stop-reread,regression-self-check,notify-strange-stop}.sh
#
# 🔒 불변 안전 (위반 = 전 봇 trap): 모든 훅 fail-open.
#   - 감지 불확실 / 예외 / 의존성(jq 등) 부재 → 통과(allow / exit 0).
#   - Stop 훅 surface = {"decision":"block","reason":TEXT}(1턴 연장+지시 주입)만 유효.
#     그 외 출력은 모델에 도달하지 않음 → 정상 종료는 출력 없이 exit 0.
#   - PreToolUse 차단 = exit 2 + stderr. 통과 = exit 0.
#   - 재귀가드(stop_hook_active): block 후 재진입 시 allow (무한루프 차단).

# ── 입력 ──────────────────────────────────────────────
# stdin JSON 1회 읽어 HK_INPUT 에 보관 (없거나 깨져도 안전)
hk_read_input() { HK_INPUT="$(cat 2>/dev/null || true)"; }

# hk_json <jq-filter>: HK_INPUT 에 jq 적용. jq 부재/파싱실패 → 빈 문자열(=안전)
hk_json() {
  command -v jq >/dev/null 2>&1 || { printf ''; return 0; }
  printf '%s' "${HK_INPUT:-}" | jq -r "$1" 2>/dev/null || printf ''
}

# ── 시각 ──────────────────────────────────────────────
hk_now_kst() { TZ="Asia/Seoul" date "+%Y-%m-%d %H:%M KST"; }

# ── 봇 정체성 ─────────────────────────────────────────
# DISCORD_STATE_DIR basename - 'discord-' / Codex 는 CODEX_BOT. 비-봇 세션이면 빈 문자열.
hk_bot() {
  if [ -n "${CODEX_BOT:-}" ]; then printf '%s' "$CODEX_BOT"; return 0; fi
  if [ -n "${DISCORD_STATE_DIR:-}" ]; then basename "$DISCORD_STATE_DIR" 2>/dev/null | sed 's/^discord-//'; return 0; fi
  printf ''
}

# 반복운영루프(무인 자동화) 세션인가? → 0(자동화) / 1(아님)
# autonomy.md §2 "반복 운영 루프(AK-Tofu 일상 파이프라인)만 제외" 구현.
# 마커: 명시 env(HK_AUTOMATION) 또는 봇 이름이 HK_AUTOMATION_BOTS(콤마 구분 목록)에 포함.
hk_is_automation() {
  [ -n "${HK_AUTOMATION:-}" ] && return 0
  local _b; _b="$(hk_bot)"
  if [ -n "$_b" ] && [ -n "${HK_AUTOMATION_BOTS:-}" ]; then
    case ",${HK_AUTOMATION_BOTS}," in *",${_b},"*) return 0 ;; esac
  fi
  return 1
}

# ── audit 로그 ────────────────────────────────────────
hk_log() {
  local d="$HOME/.claude/audit/hooks"
  mkdir -p "$d" 2>/dev/null || return 0
  printf '%s | %s | %s\n' "$(hk_now_kst)" "$(hk_bot)" "$1" >> "$d/$(date +%Y%m%d).log" 2>/dev/null || true
}

# ── Stop 훅 헬퍼 ──────────────────────────────────────
# 재귀가드: stop_hook_active==true 면 0(재귀중) → 호출측은 반드시 allow.
hk_stop_active() { [ "$(hk_json '.stop_hook_active // false')" = "true" ]; }
# 트랜스크립트 경로
hk_transcript() { hk_json '.transcript_path // empty'; }

# ── 결정 emit ─────────────────────────────────────────
# Stop: 1턴 연장 + 지시 주입 ({"decision":"block","reason":TEXT})
hk_block_stop() {
  command -v jq >/dev/null 2>&1 || exit 0
  printf '%s' "$1" | jq -R -s '{decision:"block", reason:.}' 2>/dev/null || exit 0
  exit 0
}
# Stop: 정상 종료 허용
hk_allow_stop() { exit 0; }
# PreToolUse: 차단 / 통과
# 현재 계약(2026-05 claude-code-guide 확인): deny = JSON hookSpecificOutput.permissionDecision="deny" + exit 0.
#   (exit 2 는 legacy — stderr 가 모델 아닌 사용자에게만 가서 봇이 사유를 못 읽음.)
# jq 부재 시 allow(fail-open).
hk_deny() {
  command -v jq >/dev/null 2>&1 || exit 0
  printf '%s' "soft→hard 훅 차단: $1" | jq -R -s '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:.}}' 2>/dev/null || exit 0
  exit 0
}
hk_allow() { exit 0; }

# ── fail-open backstop (각 훅 source 직후 호출) ──────────
# 예외/ERR 시 무조건 안전 종료(exit 0=allow). block/deny 는 명시 경로에서만 도달.
hk_failopen() { set -uo pipefail; trap 'exit 0' ERR; }
