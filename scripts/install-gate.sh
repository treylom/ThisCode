#!/usr/bin/env bash
# install-gate.sh — 「수동 안내를 띄워도 되는가」를 답하는 게이트 + 그 답변의 원장 (R2·R4)
#
# 왜 스크립트인가: 이 규칙을 스킬 문서에만 적으면 «안 밟힌다». 오늘 밤 반복 확인된
#   「지식 ≠ 강제」. 수동 안내를 내보내려는 «순간» 이 명령을 실제로 부르게 만든다.
#
# 왜 원장인가: 01-spec.md 의 R2 합격 기준은 「자동 시도 1회 + **그 결과 기록**」이다.
#   기록이 없으면 그 기준은 «판정 불가»다 — 기준을 써놓고 판정할 수단을 안 만들면
#   그 기준은 검토를 면제받는다. (2026-08-13 자기적발. 손석희의 ThisCodex 쪽
#   automation-gate 감사 JSONL 설계를 채택 — 두 제품이 같은 모양이어야 한다.)
#
# 사용:
#   bash scripts/install-gate.sh <관문이름>
#     exit 0 — 수동 안내 OK (명단 등재 관문이거나 사용자가 manual 모드를 골랐다)
#     exit 1 — 먼저 자동으로 «한 번 시도»할 것. 실패했을 때만 안내한다
#     exit 2 — 모르는 관문 이름 / 계약 파일 없음 → 기본값은 시도(호출자는 1 과 같게 취급)
#
#   bash scripts/install-gate.sh --attempted <관문이름> <ok|fail> [사유]
#     시도했다는 «사실»을 원장에 남긴다. fail 인데 사유가 비면 exit 2 —
#     사유 없는 낙하는 계약 위반이라 기록 자체를 거부한다.
#
#   bash scripts/install-gate.sh --audit
#     원장을 되감아 「시도하라(exit 1)는 판정을 받고도 시도 기록이 없는 관문」을 나열.
#     exit 0 = 위반 0 / exit 1 = 위반 있음.
#
# 설계 메모: 「모르는 이름」을 통과(0)로 두면 새 관문이 조용히 수동으로 샌다.
#   기본값이 이기고, 기본값은 흔한 쪽이다 — 그래서 기본값을 «시도» 쪽에 둔다.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$HERE/../configs/install.yaml"
STATE="${THISCODE_INSTALL_STATE:-$HOME/.thiscode/install-state.yaml}"
LEDGER="${THISCODE_INSTALL_LOG:-$HOME/.thiscode/install-log.jsonl}"

# ── 원장 ────────────────────────────────────────────────────────────
# jq 의존 없이 한 줄 JSON 을 만든다. 값에 들어갈 수 있는 것은 " \ 와 제어문자뿐이라
# 그 셋만 막으면 형식이 깨지지 않는다.
_json_escape() {
  printf '%s' "$1" | LC_ALL=C tr -d '\000-\037' | command sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

_ledger_append() {   # $1=kind $2=gate $3=verdict/outcome $4=detail
  local dir ts
  dir="$(dirname "$LEDGER")"
  mkdir -p "$dir" 2>/dev/null || return 0     # 기록 실패가 설치를 막지는 않는다
  ts="$(date +%Y-%m-%dT%H:%M:%S%z)"
  printf '{"ts":"%s","kind":"%s","gate":"%s","result":"%s","detail":"%s"}\n' \
    "$ts" "$(_json_escape "$1")" "$(_json_escape "$2")" \
    "$(_json_escape "$3")" "$(_json_escape "${4:-}")" >> "$LEDGER" 2>/dev/null || true
}

_mode() {
  local m=""
  [ -f "$STATE" ] && m="$(command sed -n 's/^[[:space:]]*mode:[[:space:]]*\([a-z]*\).*/\1/p' "$STATE" | head -1)"
  if [ -z "$m" ] && [ -f "$CONFIG" ]; then
    m="$(command sed -n 's/^[[:space:]]*default_mode:[[:space:]]*\([a-z]*\).*/\1/p' "$CONFIG" | head -1)"
  fi
  [ -z "$m" ] && m="auto"
  printf '%s' "$m"
}

# ── --attempted: 시도 사실을 남긴다 ─────────────────────────────────
if [ "${1:-}" = "--attempted" ]; then
  gate="${2:-}"; outcome="${3:-}"; reason="${4:-}"
  if [ -z "$gate" ] || { [ "$outcome" != "ok" ] && [ "$outcome" != "fail" ]; }; then
    echo "usage: install-gate.sh --attempted <관문이름> <ok|fail> [사유]" >&2
    exit 2
  fi
  if [ "$outcome" = "fail" ] && [ -z "$reason" ]; then
    echo "install-gate: 실패를 사유 없이 기록할 수 없다 — 사유 없는 수동 낙하는 계약 위반 ($gate)" >&2
    exit 2
  fi
  _ledger_append "attempt" "$gate" "$outcome" "$reason"
  echo "시도 기록됨 — $gate = $outcome${reason:+ ($reason)}"
  exit 0
fi

# ── --audit: 계약이 지켜졌는지 되감아 본다 ──────────────────────────
# 🔴 이 감사가 답하는 질문은 «정확히» 이것 하나다:
#     「exit 1(=먼저 시도하라) 판정을 받고도, 그 뒤에 그 관문에 대한 시도 기록이
#       없는 관문은 무엇인가」
#   답하지 «않는» 것: 수동 안내가 화면에 실제로 떴는지. 게이트는 그걸 볼 수 없다.
#   그러므로 위반 0 은 「계약 준수」가 아니라 「미이행 흔적 없음」이다.
if [ "${1:-}" = "--audit" ]; then
  if [ ! -f "$LEDGER" ]; then
    echo "원장 없음 — $LEDGER (아직 게이트가 한 번도 안 불렸다)"
    exit 0
  fi
  viol=0
  # 관문별로: 마지막 'attempt-required' 판정 이후에 attempt 기록이 있는가
  gates="$(command sed -n 's/.*"gate":"\([^"]*\)".*/\1/p' "$LEDGER" | sort -u)"
  for g in $gates; do
    [ -z "$g" ] && continue
    last_req="$(command grep -n "\"gate\":\"$g\"" "$LEDGER" | command grep '"result":"attempt-required"' | tail -1 | cut -d: -f1)"
    [ -z "$last_req" ] && continue
    last_try="$(command grep -n "\"gate\":\"$g\"" "$LEDGER" | command grep '"kind":"attempt"' | tail -1 | cut -d: -f1)"
    if [ -z "$last_try" ] || [ "$last_try" -lt "$last_req" ]; then
      echo "위반 — $g: 「먼저 시도하라」 판정(원장 $last_req 행) 뒤에 시도 기록이 없다"
      viol=$((viol + 1))
    fi
  done
  echo "감사 질문: exit 1 을 받고도 시도 기록이 없는 관문. (수동 안내가 실제로 떴는지는 이 감사로 알 수 없다)"
  echo "위반 $viol 건 / 원장 $(command wc -l < "$LEDGER" | tr -d ' ') 행"
  [ "$viol" -eq 0 ] || exit 1
  exit 0
fi

# ── 게이트 본체 (종료코드 계약 불변) ────────────────────────────────
GATE="${1:-}"
if [ -z "$GATE" ]; then
  echo "usage: install-gate.sh <관문이름>" >&2
  exit 2
fi

if [ ! -f "$CONFIG" ]; then
  echo "install-gate: 계약 파일 없음 — $CONFIG" >&2
  _ledger_append "gate" "$GATE" "no-config" "$CONFIG"
  exit 2
fi

mode="$(_mode)"

# manual 모드면 사람이 직접 하겠다고 고른 것이다 — 안내를 막지 않는다.
if [ "$mode" = "manual" ]; then
  echo "manual 모드 — 안내 허용 ($GATE)"
  _ledger_append "gate" "$GATE" "allowed" "manual-mode"
  exit 0
fi

# ── auto 모드: 명단 등재 여부로만 판정 ──────────────────────────────
# 명단은 `- name: <이름>` 형태. 이름만 뽑아 «완전 일치»로 본다
# (부분 일치로 보면 discord_hcaptcha 가 discord_hcaptcha_v2 를 덮어 새 관문이 샌다).
if command sed -n 's/^[[:space:]]*-[[:space:]]*name:[[:space:]]*\([A-Za-z0-9_]*\).*/\1/p' "$CONFIG" \
   | command grep -qx -- "$GATE"; then
  echo "등재된 관문 — 안내 허용 ($GATE, mode=$mode)"
  _ledger_append "gate" "$GATE" "allowed" "listed"
  exit 0
fi

# 명단에 없다 = 아직 시도해보지 않아도 되는 이유가 «선언되지 않았다»
echo "미등재 관문 — 먼저 자동으로 한 번 시도할 것 ($GATE, mode=$mode)" >&2
echo "  시도한 뒤 반드시: bash scripts/install-gate.sh --attempted $GATE <ok|fail> [사유]" >&2
_ledger_append "gate" "$GATE" "attempt-required" "unlisted"
exit 1
