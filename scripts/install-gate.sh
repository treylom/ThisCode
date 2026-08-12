#!/usr/bin/env bash
# install-gate.sh — 「수동 안내를 띄워도 되는가」를 답하는 게이트 (R2·R4)
#
# 왜 스크립트인가: 이 규칙을 스킬 문서에만 적으면 «안 밟힌다». 오늘 밤 반복 확인된
#   「지식 ≠ 강제」. 수동 안내를 내보내려는 «순간» 이 명령을 실제로 부르게 만든다.
#
# 사용:  bash scripts/install-gate.sh <관문이름>
#   exit 0 — 수동 안내 OK (명단 등재 관문이거나 사용자가 manual 모드를 골랐다)
#   exit 1 — 먼저 자동으로 «한 번 시도»할 것. 실패했을 때만 안내한다
#   exit 2 — 모르는 관문 이름 → 기본값은 시도(호출자는 1 과 같게 취급할 것)
#
# 설계 메모: 「모르는 이름」을 통과(0)로 두면 새 관문이 조용히 수동으로 샌다.
#   기본값이 이기고, 기본값은 흔한 쪽이다 — 그래서 기본값을 «시도» 쪽에 둔다.

set -uo pipefail

GATE="${1:-}"
if [ -z "$GATE" ]; then
  echo "usage: install-gate.sh <관문이름>" >&2
  exit 2
fi

# 계약 파일 = 이 스크립트의 형제 디렉터리. 플러그인이 어디에 설치돼도 따라온다.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$HERE/../configs/install.yaml"
STATE="${THISCODE_INSTALL_STATE:-$HOME/.thiscode/install-state.yaml}"

if [ ! -f "$CONFIG" ]; then
  echo "install-gate: 계약 파일 없음 — $CONFIG" >&2
  exit 2
fi

# ── 모드 결정: 런타임 상태 > 배포 기본값 ────────────────────────────
mode=""
[ -f "$STATE" ] && mode="$(sed -n 's/^[[:space:]]*mode:[[:space:]]*\([a-z]*\).*/\1/p' "$STATE" | head -1)"
if [ -z "$mode" ]; then
  mode="$(sed -n 's/^[[:space:]]*default_mode:[[:space:]]*\([a-z]*\).*/\1/p' "$CONFIG" | head -1)"
fi
[ -z "$mode" ] && mode="auto"

# manual 모드면 사람이 직접 하겠다고 고른 것이다 — 안내를 막지 않는다.
if [ "$mode" = "manual" ]; then
  echo "manual 모드 — 안내 허용 ($GATE)"
  exit 0
fi

# ── auto 모드: 명단 등재 여부로만 판정 ──────────────────────────────
# 명단은 `- name: <이름>` 형태. 이름만 뽑아 «완전 일치»로 본다
# (부분 일치로 보면 discord_hcaptcha 가 discord_hcaptcha_v2 를 덮어 새 관문이 샌다).
if sed -n 's/^[[:space:]]*-[[:space:]]*name:[[:space:]]*\([A-Za-z0-9_]*\).*/\1/p' "$CONFIG" \
   | grep -qx -- "$GATE"; then
  echo "등재된 관문 — 안내 허용 ($GATE, mode=$mode)"
  exit 0
fi

# 명단에 없다 = 아직 시도해보지 않아도 되는 이유가 «선언되지 않았다»
echo "미등재 관문 — 먼저 자동으로 한 번 시도할 것 ($GATE, mode=$mode)" >&2
exit 1
