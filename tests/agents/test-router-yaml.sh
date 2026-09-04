#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCHEMA="$ROOT/schemas/agent-spec.json"
AJV_OPTS="--spec=draft2019 --strict=false -c ajv-formats"

ajv validate -s "$SCHEMA" -d "$ROOT/.agents/model-router.yaml" $AJV_OPTS || { echo "FAIL: router yaml schema"; exit 1; }
yq -e '.tier == "external"' "$ROOT/.agents/model-router.yaml" >/dev/null
yq -e '.provides_tools | contains(["claude_discode_route_model"])' "$ROOT/.agents/model-router.yaml" >/dev/null
echo "PASS router yaml"
