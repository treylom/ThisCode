#!/usr/bin/env bash
# Dogfood orchestrator — run the sandbox scenarios + report.
set -e

ROOT="${CLAUDE_DISCODE_HOME:-/thiscode}"
HERE="$ROOT/tests/dogfood"
LOG="$HERE/dogfood-results-$(date +%Y-%m-%d).md"

{
  echo "# Dogfood Results — $(date +%Y-%m-%d-%H%M)"
  echo
  echo "Host: $(uname -a)"
  echo "Vault: ${CLAUDE_DISCODE_VAULT:-not set}"
  echo
} > "$LOG"

pass=0; fail=0
for s in scenario-2-mcp.sh scenario-3-graphrag.sh; do
  echo "=== $s ==="
  if bash "$HERE/$s"; then
    pass=$((pass + 1))
    echo "- $s: PASS" >> "$LOG"
  else
    fail=$((fail + 1))
    echo "- $s: FAIL" >> "$LOG"
  fi
done

{
  echo
  echo "## Summary"
  echo "- PASS: $pass"
  echo "- FAIL: $fail"
} >> "$LOG"

echo
echo "Results recorded: $LOG"
[ "$fail" = "0" ] || exit 1
