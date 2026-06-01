#!/bin/bash
set -uo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$BASE/../../scripts/memory_s5.py" ]; then
  ROOT="$(cd "$BASE/../.." && pwd)"
else
  ROOT="$(cd "$BASE/../../.." && pwd)"
fi
if [ -f "$ROOT/.claude/scripts/memory_s5.py" ]; then
  SCRIPT="$ROOT/.claude/scripts/memory_s5.py"
  PREPROMPT="$ROOT/.claude/hooks/memory-s5-preprompt.sh"
else
  SCRIPT="$ROOT/scripts/memory_s5.py"
  PREPROMPT="$ROOT/hooks/memory-s5-preprompt.sh"
fi
fail=0

check_score() {
  local name="$1" text="$2" expected="$3"
  local got
  got="$(python3 "$SCRIPT" score "$text" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)["trigger"]).lower())')"
  if [ "$got" = "$expected" ]; then
    printf '  PASS  %-34s trigger=%s\n' "$name" "$got"
  else
    printf '  FAIL  %-34s expect=%s got=%s\n' "$name" "$expected" "$got"
    fail=$((fail+1))
  fi
}

check_contains() {
  local name="$1" text="$2" needle="$3"
  local out
  out="$(printf '{"prompt":%s}' "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1], ensure_ascii=False))' "$text")" | bash "$PREPROMPT")"
  if printf '%s' "$out" | grep -q "$needle"; then
    printf '  PASS  %-34s contains=%s\n' "$name" "$needle"
  else
    printf '  FAIL  %-34s missing=%s\n' "$name" "$needle"
    fail=$((fail+1))
  fi
}

check_empty() {
  local name="$1" text="$2"
  local out
  out="$(printf '{"prompt":%s}' "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1], ensure_ascii=False))' "$text")" | bash "$PREPROMPT")"
  if [ -z "$out" ]; then
    printf '  PASS  %-34s empty\n' "$name"
  else
    printf '  FAIL  %-34s expected-empty got=%s\n' "$name" "$out"
    fail=$((fail+1))
  fi
}

check_score "keyword-trigger" "지난번처럼 고쳐줘" true
check_score "weak-single-no-trigger" "다시 빌드해줘" false
check_score "weak-plus-task-trigger" "다시 수정해줘" true
check_contains "preprompt-trigger" "지난번처럼 고쳐줘" "MEMORY §5 TRIGGERED"
check_empty "preprompt-no-trigger" "다시 빌드해줘"

echo "----------------------------------------"
if [ "$fail" = 0 ]; then
  echo "MEMORY_S5_PASS=5 FAIL=0"
else
  echo "MEMORY_S5_FAIL=$fail"
fi
[ "$fail" = 0 ]
