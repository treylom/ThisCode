#!/usr/bin/env bash
# bot-only.sh — 봇 세션에서만 대상 훅을 실행하는 얇은 래퍼 (플러그인 hooks.json 전용)
#
# 왜 있나: 플러그인의 hooks/hooks.json 은 «모든» Claude Code 세션에 훅을 싣는다.
#   그런데 이 제품의 훅 7종은 봇 운영용이다 — 일반 개발 세션에 답장 게이트나 규칙
#   라우터가 붙으면 그건 기능이 아니라 부작용이다. 그래서 훅 5개에 가드를 각각
#   심는 대신, 실행 «앞»에 한 곳을 둔다. 훅이 늘어도 이 파일 하나가 계속 막는다.
#
# 판정 필드: DISCORD_STATE_DIR — 봇 정체성의 정본 필드다(hooks/lib/hookkit.sh 의
#   hk_bot() 이 같은 필드로 봇 이름을 뽑는다). 비어 있으면 = 봇 세션이 아니다.
#
# 계약:
#   봇 세션 아님 → stdin 을 비우고 stdout 0 바이트로 exit 0 (무동작·무출력).
#   봇 세션     → 첫 인자 = 실행할 훅 경로, 나머지 인자는 그대로 넘긴다.
#                 *.py → python3 · 그 외 → bash. stdin 은 exec 로 자연히 이어지고
#                 종료코드도 대상의 것이 그대로 나간다.
#   대상 파일 부재 → stderr 한 줄 + exit 0 (fail-open — 훅 하나가 세션을 막지 않는다,
#                 hookkit.sh 의 hk_failopen 과 같은 방향).
#
# 사용: bash bot-only.sh <훅 경로> [인자...]
# 이식성: bash 3.2(macOS 기본)에서 동작한다.

set -u

# stdin 을 비운다 — 훅 입력 JSON 이 파이프에 남으면 상류가 EPIPE 를 본다.
# 터미널(tty)에서는 비울 것이 없고 cat 이 멈춰 서므로 건너뛴다.
_drain_stdin() { [ -t 0 ] || cat >/dev/null 2>&1 || true; }

if [ -z "${DISCORD_STATE_DIR:-}" ]; then
  _drain_stdin
  exit 0
fi

target="${1:-}"
if [ -z "$target" ]; then
  _drain_stdin
  echo "bot-only: 실행할 훅 경로가 인자로 오지 않았다" >&2
  exit 0
fi
shift

if [ ! -f "$target" ]; then
  _drain_stdin
  echo "bot-only: 훅 파일이 실재하지 않는다 — $target" >&2
  exit 0
fi

case "$target" in
  *.py) exec python3 "$target" "$@" ;;
  *)    exec bash "$target" "$@" ;;
esac
