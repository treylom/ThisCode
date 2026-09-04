#!/usr/bin/env bash
# test-all-yamls.sh — every .agents/*.yaml passes schema + minimum count check
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCHEMA="$ROOT/schemas/agent-spec.json"
AJV_OPTS="--spec=draft2019 --strict=false -c ajv-formats"

COUNT=0
FAIL=0
for f in "$ROOT"/.agents/*.yaml; do
  [ -e "$f" ] || continue
  COUNT=$((COUNT + 1))
  if ! ajv validate -s "$SCHEMA" -d "$f" $AJV_OPTS >/dev/null 2>&1; then
    echo "FAIL: $f"
    ajv validate -s "$SCHEMA" -d "$f" $AJV_OPTS 2>&1 | sed 's/^/  /'
    FAIL=1
  fi
done

# 6 expected after 1.4.0 (bootstrap, codex-exec-bridge, init, meetings,
# model-router, shared-memory) — measured, not guessed.
if [ "$COUNT" -lt 6 ]; then
  echo "FAIL: expected 6+ agents, got $COUNT"
  exit 1
fi

if [ "$FAIL" = "0" ]; then
  echo "PASS all yamls (count=$COUNT)"
fi
exit "$FAIL"
