#!/usr/bin/env bash
# Test: km-version.sh detects version drift and rejects bad contract metadata.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/km-version.sh"
FIXTURE_ROOT=$(mktemp -d)

cleanup() {
  find "$FIXTURE_ROOT" -type f -exec unlink {} + 2>/dev/null || true
  find "$FIXTURE_ROOT" -depth -type d -exec rmdir {} + 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$FIXTURE_ROOT/plugin/contracts" "$FIXTURE_ROOT/vault/.claude/reference/contracts"

run_check() {
  CLAUDE_DISCODE_HOME="$FIXTURE_ROOT/plugin" CLAUDE_DISCODE_VAULT="$FIXTURE_ROOT/vault" \
    bash "$SCRIPT"
}

write_contracts() {
  local plugin_version="$1"
  local vault_version="$2"
  cat > "$FIXTURE_ROOT/plugin/contracts/sample.md" <<EOF
---
contract: sample
version: $plugin_version
date: 2026-09-05
---
EOF
  cat > "$FIXTURE_ROOT/vault/.claude/reference/contracts/sample.md" <<EOF
---
contract: sample
version: $vault_version
date: 2026-09-05
---
EOF
}

# Matching versions pass.
write_contracts 0.1.0 0.1.0
OUTPUT=$(run_check 2>&1)
echo "$OUTPUT" | grep -q "ok: 0.1.0 == 0.1.0 (sample.md)" || {
  echo "FAIL: same version check"
  exit 1
}

# A version mismatch is a drift warning and a non-zero result.
write_contracts 0.1.0 0.2.0
set +e
OUTPUT=$(run_check 2>&1)
STATUS=$?
set -e
[ "$STATUS" -ne 0 ] || { echo "FAIL: mismatch returned success"; exit 1; }
echo "$OUTPUT" | grep -q "WARNING: drift — sample.md plugin=0.1.0 vault=0.2.0" || {
  echo "FAIL: drift detection"
  exit 1
}

# Missing plugin metadata must fail; it must not compare empty strings.
write_contracts 0.1.0 0.1.0
awk '!/^version:/' "$FIXTURE_ROOT/plugin/contracts/sample.md" \
  > "$FIXTURE_ROOT/plugin/contracts/sample.tmp"
mv "$FIXTURE_ROOT/plugin/contracts/sample.tmp" "$FIXTURE_ROOT/plugin/contracts/sample.md"
set +e
OUTPUT=$(run_check 2>&1)
STATUS=$?
set -e
[ "$STATUS" -ne 0 ] || { echo "FAIL: missing plugin version returned success"; exit 1; }
echo "$OUTPUT" | grep -q "ERROR: invalid or missing version metadata — plugin contract sample.md" || {
  echo "FAIL: missing plugin version diagnostic"
  exit 1
}
! echo "$OUTPUT" | grep -q "ok:  ==" || { echo "FAIL: empty versions compared as equal"; exit 1; }

# Both sides missing metadata must also fail closed.
write_contracts 0.1.0 0.1.0
for contract_file in \
  "$FIXTURE_ROOT/plugin/contracts/sample.md" \
  "$FIXTURE_ROOT/vault/.claude/reference/contracts/sample.md"; do
  awk '!/^version:/' "$contract_file" > "$contract_file.tmp"
  mv "$contract_file.tmp" "$contract_file"
done
set +e
OUTPUT=$(run_check 2>&1)
STATUS=$?
set -e
[ "$STATUS" -ne 0 ] || { echo "FAIL: both missing versions returned success"; exit 1; }
! echo "$OUTPUT" | grep -q "ok:  ==" || { echo "FAIL: both empty versions compared as equal"; exit 1; }

# Malformed vault metadata must fail as well.
write_contracts 0.1.0 not-a-version
set +e
OUTPUT=$(run_check 2>&1)
STATUS=$?
set -e
[ "$STATUS" -ne 0 ] || { echo "FAIL: malformed vault version returned success"; exit 1; }
echo "$OUTPUT" | grep -q "ERROR: invalid or missing version metadata — vault contract sample.md" || {
  echo "FAIL: malformed vault version diagnostic"
  exit 1
}

# A missing mirror directory retains the existing non-zero optional-mirror path.
set +e
OUTPUT=$(CLAUDE_DISCODE_HOME="$FIXTURE_ROOT/plugin" CLAUDE_DISCODE_VAULT="$FIXTURE_ROOT/no-vault" \
  bash "$SCRIPT" 2>&1)
STATUS=$?
set -e
[ "$STATUS" -eq 2 ] || { echo "FAIL: missing mirror status"; exit 1; }
echo "$OUTPUT" | grep -q "vault mirror missing: .* — copy or sync contracts from .* into this destination before rerunning" || {
  echo "FAIL: missing mirror remediation"
  exit 1
}
echo "$OUTPUT" | grep -q "no ThisCode installer or /km:setup creates contract mirrors" || {
  echo "FAIL: missing mirror producer boundary"
  exit 1
}
! echo "$OUTPUT" | grep -q '/thiscode:km-bootstrap' || {
  echo "FAIL: missing mirror points to non-producing bootstrap command"
  exit 1
}

echo "PASS"
