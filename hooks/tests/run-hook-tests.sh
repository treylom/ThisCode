#!/bin/bash
# run-hook-tests.sh — soft→hard 훅 격리 테스트 하니스.
#
# cases/<name>/ 디렉토리 순회:
#   input.json  (옵션) stdin 으로 hook 에 전달할 mock payload. 없으면 '{}'.
#   cmd         (필수) 실행할 명령. 예: bash "$HOOKS_DIR/reply-gate.sh"
#   expect      (필수) 기대 결과: deny | block | allow
#   env         (옵션) 줄당 KEY=VALUE — hook 실행 시 주입할 환경변수
#
# 분류: exit 2 → deny / stdout 에 {"decision":...:"block"} → block / 그 외 → allow
# 등록 전 PASS 필수.

set -uo pipefail
export HOOKS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CASES_DIR="$(cd "$(dirname "$0")" && pwd)/cases"
pass=0; fail=0
declare -a failures=()

for c in "$CASES_DIR"/*/; do
  [ -d "$c" ] || continue
  name="$(basename "$c")"
  [ -f "$c/cmd" ] || continue
  expect="$(tr -d '[:space:]' < "$c/expect" 2>/dev/null)"
  if [ -f "$c/input.json" ]; then
    input="$(sed -e "s#__CASEDIR__#${c%/}#g" -e "s#__HOME__#$HOME#g" "$c/input.json")"
  else input='{}'; fi
  cmd="$(cat "$c/cmd")"
  envargs=()
  if [ -f "$c/env" ]; then
    while IFS= read -r line || [ -n "$line" ]; do [ -n "$line" ] && envargs+=("$line"); done < "$c/env"
  fi
  errf="$(mktemp)"
  out="$(printf '%s' "$input" | env ${envargs[@]+"${envargs[@]}"} bash -c "$cmd" 2>"$errf")"; code=$?
  rm -f "$errf" 2>/dev/null
  if printf '%s' "$out" | grep -qE '"permissionDecision"[[:space:]]*:[[:space:]]*"deny"'; then got=deny
  elif [ "$code" = "2" ]; then got=deny
  elif printf '%s' "$out" | grep -qE '"decision"[[:space:]]*:[[:space:]]*"block"'; then got=block
  else got=allow; fi
  if [ "$got" = "$expect" ]; then
    pass=$((pass+1)); printf '  PASS  %-28s %s\n' "$name" "$got"
  else
    fail=$((fail+1)); failures+=("$name expect=$expect got=$got"); printf '  FAIL  %-28s expect=%s got=%s\n' "$name" "$expect" "$got"
  fi
done

echo "----------------------------------------"
echo "PASS=$pass FAIL=$fail"
[ "$fail" = "0" ]
