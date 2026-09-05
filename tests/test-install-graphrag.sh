#!/usr/bin/env bash
# Test: install-graphrag.sh detects Python venv requirements and exits cleanly on missing deps.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/install-graphrag.sh"

# Case A: --check prints required deps
OUT=$(bash "$SCRIPT" --check 2>&1 || true)
echo "$OUT" | grep -qE "python3:|venv:|requirements:" \
  || { echo "FAIL: deps listed missing"; exit 1; }

# Case B: invoking with --check should exit ≤4 (4 means python3 missing, 0 means OK)
set +e
PATH="/usr/bin:/bin" bash "$SCRIPT" --check >/dev/null 2>&1
RC=$?
set -e
[ "$RC" -le 4 ] || { echo "FAIL: rc=$RC"; exit 1; }

echo "PASS"
