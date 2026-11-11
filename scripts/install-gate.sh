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
#   bash scripts/install-gate.sh --attempted <관문이름> <ok|fail> [사유 코드]
#     시도했다는 «사실»을 원장에 남긴다. fail 인데 사유가 비면 exit 2 —
#     사유 없는 낙하는 계약 위반이라 기록 자체를 거부한다.
#     사유는 정해진 코드만 받는다(그 밖 = exit 2). 목록 = configs/install.yaml 의 attempt_reason_codes.
#     기록 파일을 안전하게 쓸 수 없으면(심볼릭 링크 · 일반 파일 아님 · 소유자 다름) exit 3.
#   bash scripts/install-gate.sh --reason-codes
#     받는 사유 코드와, 사용자에게 넘길 때 쓰는 정해진 문장을 한 줄씩 보여 준다.
#
#   bash scripts/install-gate.sh --handoff <관문이름>
#     막힌 단계를 사람에게 넘기기 «직전»에 부른다.
#     exit 0 — 넘겨도 된다 (사람만 하는 자리 · manual 모드 · 자동 시도 N회 실패 기록됨)
#     exit 1 — 아직 아니다. 다음 자동 시도가 무엇인지 알려 준다 (N = install.yaml, 기본 3)
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

# ── 설치 기록 파일을 지키는 법 ──────────────────────────────────────
# 본인만 읽고 쓴다: 폴더 0700 · 파일 0600 을 호출자의 umask 와 상관없이 매번 맞추고 다시 확인한다.
# 쓰기 전에 보는 것(순서대로): 폴더가 심볼릭 링크가 아닌 진짜 폴더이고 지금 사용자 것인가 →
#   파일 자리가 심볼릭 링크가 아닌가(권한을 낮추기 «전»에 본다) → 일반 파일 · 지금 사용자 것 · 하드 링크 1 인가.
# 하나라도 아니면 쓰지도 읽지도 않고 1 을 돌려준다(성공인 척하지 않는다).
# 남는 틈: bash 만으로는 «한 번 연 파일을 확인하고 그 손잡이에 쓰기»(O_NOFOLLOW + fstat)를 못 한다.
#   확인과 덧붙이기 사이에 «같은 사용자»의 다른 프로세스가 파일을 바꿔치면 막지 못한다.
#   다른 사용자는 0700 폴더에 들어올 수 없어 바꿔칠 수 없다. 덧붙인 뒤 링크 여부를 한 번 더 본다.
_modes_meaningful() {   # 윈도우 git-bash 는 권한 비트가 뜻이 없다(거긴 파일 ACL 이 따로 있다)
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*) return 1 ;;
  esac
  return 0
}

_stat_mode_links() {   # "<8진 권한> <하드 링크 수>" — GNU stat 먼저, 아니면 BSD stat
  command stat -c '%a %h' "$1" 2>/dev/null || command stat -f '%Lp %l' "$1" 2>/dev/null
}

_ledger_dir_ready() {   # $1=make → 없으면 만든다
  local dir created=0 info mode
  dir="$(dirname "$LEDGER")"
  [ -L "$dir" ] && return 1
  if [ ! -e "$dir" ]; then
    [ "${1:-}" = "make" ] || return 0
    ( umask 077; mkdir -p "$dir" ) 2>/dev/null || return 1
    created=1
  fi
  [ -L "$dir" ] && return 1
  [ -d "$dir" ] && [ -O "$dir" ] || return 1
  _modes_meaningful || return 0
  if [ "$created" = 1 ] || [ "$(basename "$dir")" = ".thiscode" ]; then
    # 우리 폴더(~/.thiscode 또는 방금 만든 폴더)는 0700 으로 맞춘다
    chmod 700 "$dir" 2>/dev/null || return 1
    info="$(_stat_mode_links "$dir")" || return 1
    [ "${info%% *}" = "700" ] || return 1
  elif [ "${1:-}" = "make" ]; then
    # THISCODE_INSTALL_LOG 로 남의 폴더를 가리킨 경우: 그 폴더 권한은 바꾸지 않는다.
    # 대신 남이 쓸 수 있는 폴더면(그룹·기타 쓰기) 거기에는 쓰지 않는다.
    info="$(_stat_mode_links "$dir")" || return 1
    mode="${info%% *}"
    case "$mode" in
      *[2367]?|*[2367]) return 1 ;;
    esac
  fi
  return 0
}

_ledger_file_ok() {   # 지금 있는 파일이 믿을 만한가 — 심볼릭 링크를 가장 먼저 본다
  local info
  [ -L "$LEDGER" ] && return 1
  [ -f "$LEDGER" ] && [ -O "$LEDGER" ] || return 1
  info="$(_stat_mode_links "$LEDGER")" || return 1
  [ "${info##* }" = "1" ] || return 1
  return 0
}

_ledger_trusted() {   # 읽어도 되는가 (파일이 없으면 믿을 것도 없으니 참)
  _ledger_dir_ready || return 1
  [ -L "$LEDGER" ] && return 1
  [ -e "$LEDGER" ] || return 0
  _ledger_file_ok
}

_ledger_ready() {   # 써도 되는가 — 폴더·파일을 만들고 권한을 맞춘 뒤 다시 확인
  local info
  _ledger_dir_ready make || return 1
  [ -L "$LEDGER" ] && return 1
  if [ ! -e "$LEDGER" ]; then
    # noclobber = «없을 때만 새로 만든다»(그 사이 끼워 넣은 링크를 따라가지 않는다)
    ( umask 077; set -o noclobber; : > "$LEDGER" ) 2>/dev/null || return 1
  fi
  _ledger_file_ok || return 1
  _modes_meaningful || return 0
  chmod 600 "$LEDGER" 2>/dev/null || return 1
  info="$(_stat_mode_links "$LEDGER")" || return 1
  [ "${info%% *}" = "600" ] || return 1
  return 0
}

_ledger_append() {   # $1=kind $2=gate $3=verdict/outcome $4=detail — 못 쓰면 1 (성공으로 바꾸지 않는다)
  local ts
  if ! _ledger_ready; then
    echo "install-gate: 설치 기록 파일을 안전하게 쓸 수 없어 기록하지 않았다 — $LEDGER (폴더나 파일이 심볼릭 링크 · 일반 파일 아님 · 소유자 다름 · 하드 링크 여럿 · 권한을 못 낮춤 가운데 하나)" >&2
    return 1
  fi
  ts="$(date +%Y-%m-%dT%H:%M:%S%z)"
  ( umask 077
    printf '{"ts":"%s","kind":"%s","gate":"%s","result":"%s","detail":"%s"}\n' \
      "$ts" "$(_json_escape "$1")" "$(_json_escape "$2")" \
      "$(_json_escape "$3")" "$(_json_escape "${4:-}")" >> "$LEDGER" ) 2>/dev/null || {
    echo "install-gate: 설치 기록 파일에 덧붙이지 못했다 — $LEDGER" >&2
    return 1
  }
  if ! _ledger_file_ok; then
    echo "install-gate: 설치 기록 파일이 쓰는 사이 바뀌었다 — $LEDGER (이번 기록은 믿지 않는다)" >&2
    return 1
  fi
  return 0
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

# 관문 이름은 값 «전체»가 영문·숫자·밑줄이어야 한다.
# 줄바꿈·빈칸·기호가 하나라도 있으면 거부한다(줄 단위로 보면 두 줄 이름이 새어 들어온다).
_gate_name_ok() {
  local LC_ALL=C
  case "$1" in
    ''|*[!A-Za-z0-9_]*) return 1 ;;
  esac
  return 0
}

# ── 실패 사유 = 닫힌 코드 표 ─────────────────────────────────────────
# 받는 값은 아래 표의 코드뿐이다(글자 꼴이 맞아도 표에 없으면 거부). 코드마다 사용자에게 보일 문장이
# 하나씩 붙어 있고, 그 문장에 화면 글 · 오류 원문 · 값을 이어 붙이지 않는다.
# 같은 목록을 configs/install.yaml 의 attempt_reason_codes 에도 적어 두고, 시험이 둘이 같은지 본다.
REASON_CODES="element-not-found click-no-effect navigation-timeout permission-prompt login-required clipboard-empty format-mismatch tool-error install-failed network-error check-failed other"

_reason_says() {   # 코드 → 정해진 문장. 표에 없으면 1
  case "$1" in
    element-not-found)  echo "버튼이나 입력 칸을 찾지 못하는 문제" ;;
    click-no-effect)    echo "눌러도 화면이 바뀌지 않는 문제" ;;
    navigation-timeout) echo "화면이 제때 열리지 않는 문제" ;;
    permission-prompt)  echo "브라우저 권한 창이 가로막는 문제" ;;
    login-required)     echo "로그인이 필요한 문제" ;;
    clipboard-empty)    echo "복사한 값이 클립보드에 들어오지 않는 문제" ;;
    format-mismatch)    echo "받은 값의 형식이 맞지 않는 문제" ;;
    tool-error)         echo "브라우저 도구가 오류를 내는 문제" ;;
    install-failed)     echo "설치 명령이 실패하는 문제" ;;
    network-error)      echo "네트워크 연결 문제" ;;
    check-failed)       echo "설치 뒤 확인이 통과하지 않는 문제" ;;
    other)              echo "알 수 없는 문제" ;;
    *) return 1 ;;
  esac
}

_reason_code_ok() { _reason_says "$1" >/dev/null 2>&1; }

# ── --reason-codes: 받는 코드와 그 문장을 보여 준다 ─────────────────
if [ "${1:-}" = "--reason-codes" ]; then
  for code in $REASON_CODES; do
    printf '%s\t%s\n' "$code" "$(_reason_says "$code")"
  done
  exit 0
fi

# ── --attempted: 시도 사실을 남긴다 ─────────────────────────────────
if [ "${1:-}" = "--attempted" ]; then
  gate="${2:-}"; outcome="${3:-}"; reason="${4:-}"
  if ! _gate_name_ok "$gate" || { [ "$outcome" != "ok" ] && [ "$outcome" != "fail" ]; }; then
    echo "usage: install-gate.sh --attempted <관문이름> <ok|fail> [사유 코드]" >&2
    exit 2
  fi
  if [ "$outcome" = "fail" ] && [ -z "$reason" ]; then
    echo "install-gate: 실패를 사유 없이 기록할 수 없다 — 사유 없는 수동 낙하는 계약 위반 ($gate)" >&2
    exit 2
  fi
  if [ -n "$reason" ] && ! _reason_code_ok "$reason"; then
    # 받은 값은 다시 찍지 않는다 — 화면 글이나 값이 섞여 있을 수 있다.
    echo "install-gate: 사유는 정해진 코드만 받는다 — 목록: configs/install.yaml 의 attempt_reason_codes (받은 값은 기록하지 않았다)" >&2
    exit 2
  fi
  _ledger_append "attempt" "$gate" "$outcome" "$reason" || exit 3
  echo "시도 기록됨 — $gate = $outcome${reason:+ ($reason — $(_reason_says "$reason"))}"
  exit 0
fi

# ── --handoff: 막힌 단계를 사람에게 넘겨도 되는가 ───────────────────
# 답: 사람만 하는 자리(명단 등재)·manual 모드 = 바로 넘김(exit 0, 횟수에 안 넣음).
#     그 밖 = 그 관문의 «실패 시도 기록»이 N 번(configs/install.yaml
#     auto_attempts_before_handoff, 기본 3) 쌓인 뒤에만 exit 0.
#     세는 범위 = 그 관문의 마지막 성공(attempt ok)·마지막 넘김 허용 뒤.
if [ "${1:-}" = "--handoff" ]; then
  gate="${2:-}"
  if ! _gate_name_ok "$gate"; then
    echo "usage: install-gate.sh --handoff <관문이름>" >&2
    exit 2
  fi
  if [ ! -f "$CONFIG" ]; then
    echo "install-gate: 계약 파일 없음 — $CONFIG" >&2
    _ledger_append "handoff" "$gate" "no-config" "$CONFIG"
    exit 2
  fi
  need="$(command sed -n 's/^[[:space:]]*auto_attempts_before_handoff:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$CONFIG" | head -1)"
  [ -z "$need" ] && need=3
  if [ "$(_mode)" = "manual" ]; then
    echo "manual 모드 — 넘김 허용 ($gate)"
    _ledger_append "handoff" "$gate" "handoff-allowed" "manual-mode"
    exit 0
  fi
  if command sed -n 's/^[[:space:]]*-[[:space:]]*name:[[:space:]]*\([A-Za-z0-9_]*\).*/\1/p' "$CONFIG" \
     | command grep -qx -- "$gate"; then
    echo "사람만 하는 자리 — 바로 넘김 ($gate · 시도 횟수에 넣지 않는다)"
    _ledger_append "handoff" "$gate" "handoff-allowed" "human-only"
    exit 0
  fi
  fails=0
  if ! _ledger_trusted; then
    echo "install-gate: 설치 기록 파일을 믿을 수 없어 읽지 않는다 — $LEDGER (심볼릭 링크 · 일반 파일 아님 · 소유자 다름)" >&2
  elif [ -f "$LEDGER" ]; then
    fails="$(command grep -F "\"gate\":\"$gate\"" "$LEDGER" | command awk '
      /"kind":"attempt"/ && /"result":"fail"/ { n++ }
      (/"kind":"attempt"/ && /"result":"ok"/) || /"result":"handoff-allowed"/ { n = 0 }
      END { print n + 0 }')"
  fi
  if [ "$fails" -ge "$need" ]; then
    echo "자동 시도 $fails/$need 회 모두 실패 — 넘김 허용 ($gate). 넘길 때 무엇을 시도했는지 함께 말한다."
    _ledger_append "handoff" "$gate" "handoff-allowed" "after $fails failed attempts"
    exit 0
  fi
  next=$((fails + 1))
  echo "아직 넘기지 않는다 — 자동 시도 $fails/$need ($gate)" >&2
  case "$next" in
    1) echo "  시도 1: 고른 브라우저에서 화면을 다시 읽고(스냅샷) 그 단계를 다시 한다" >&2 ;;
    2) echo "  시도 2: 같은 브라우저에서 다른 길로(다른 버튼 이름·키보드·주소로 바로 가기)" >&2 ;;
    *) echo "  시도 $next: 다음 브라우저로 바꿔서(ego lite → Aside → 그 밖 — scripts/browser-detect.mjs)" >&2 ;;
  esac
  echo "  시도마다: bash scripts/install-gate.sh --attempted $gate <ok|fail> <사유 코드>   (코드 목록 = configs/install.yaml 의 attempt_reason_codes)" >&2
  _ledger_append "handoff" "$gate" "handoff-denied" "$fails/$need"
  exit 1
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
echo "  시도한 뒤 반드시: bash scripts/install-gate.sh --attempted $GATE <ok|fail> [사유 코드]" >&2
_ledger_append "gate" "$GATE" "attempt-required" "unlisted"
exit 1
