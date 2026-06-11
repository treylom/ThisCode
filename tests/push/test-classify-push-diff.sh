#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$ROOT/scripts/classify_push_diff.py"

check() {
  local expected_class="$1"; shift
  local expected_gate="$1"; shift
  local out
  out="$(python3 "$SCRIPT" --json --paths "$@")"
  python3 - "$expected_class" "$expected_gate" "$out" <<'PY'
import json, sys
expected_class, expected_gate = sys.argv[1:3]
data = json.loads(sys.argv[3])
assert data["classification"] == expected_class, data
assert data["required_gate"] == expected_gate, data
PY
}

check docs-only subset README.md docs/SETUP.md CHANGELOG.md
check docs-only subset README.ko.md docs/getting-started/guide.pdf assets/readme-banner.png
check code full scripts/install.sh docs/SETUP.md
check code full hooks/verify-before-push.sh
check none none

echo "OK"
