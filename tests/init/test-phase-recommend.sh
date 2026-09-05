#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# This fixture targets the legacy shell recommendation parser. The wrapper
# prefers the Node entry whenever `node` is visible; hide only that binary so
# this test does not silently become a test of a different product surface.
TOOL_BIN=$(mktemp -d)
trap 'rm -rf -- "$TOOL_BIN"' EXIT
for tool in bash cat jq python3; do
  ln -s "$(command -v "$tool")" "$TOOL_BIN/$tool"
done

recommend() {
  PATH="$TOOL_BIN" "$ROOT/scripts/claude-discode-init.sh" --recommend --stdin-env
}

# 3 시나리오 환경 fixture
# 시나리오 A: 빈 vault (note_count=0)
ENV_A='{"os":"darwin","vault":{"path":"/tmp/x","note_count":0},"tools":{"obsidian_cli":"","python":"/usr/bin/python3","python_version":"3.12.0","docker":"","ripgrep":"/usr/bin/rg"},"resources":{"ram_gb":16,"disk_free_gb":100}}'
OUT_A=$(echo "$ENV_A" | recommend)
echo "$OUT_A" | jq -e '.current | contains(["phase-0-obsidian", "phase-1-ripgrep"])' >/dev/null || { echo "FAIL A: phase 0,1 not in current"; exit 1; }
echo "$OUT_A" | jq -e '.later | contains(["phase-4-graphrag-optional"])' >/dev/null || { echo "FAIL A: phase-4 not optional for empty vault"; exit 1; }

# 시나리오 B: 500 노트 vault (graphrag recommend)
ENV_B='{"os":"darwin","vault":{"path":"/tmp/x","note_count":500},"tools":{"obsidian_cli":"/opt/homebrew/bin/obsidian-cli","python":"/usr/bin/python3","python_version":"3.12.0","docker":"","ripgrep":"/usr/bin/rg"},"resources":{"ram_gb":16,"disk_free_gb":100}}'
OUT_B=$(echo "$ENV_B" | recommend)
echo "$OUT_B" | jq -e '.recommended | contains(["phase-4-graphrag"])' >/dev/null || { echo "FAIL B: phase-4-graphrag not recommended at 500"; exit 1; }

# 시나리오 C: 2000+ 노트 vault (mode-r preflight)
ENV_C='{"os":"darwin","vault":{"path":"/tmp/x","note_count":2500},"tools":{"obsidian_cli":"/opt/homebrew/bin/obsidian-cli","python":"/usr/bin/python3","python_version":"3.12.0","docker":"","ripgrep":"/usr/bin/rg"},"resources":{"ram_gb":16,"disk_free_gb":100}}'
OUT_C=$(echo "$ENV_C" | recommend)
echo "$OUT_C" | jq -e '.recommended | contains(["phase-5-mode-r-preflight"])' >/dev/null || { echo "FAIL C: phase-5 not in recommended at 2500"; exit 1; }
echo "$OUT_C" | jq -e '.recommended | contains(["phase-4-graphrag-strong"])' >/dev/null || { echo "FAIL C: phase-4 not strong at 2500"; exit 1; }

echo "PASS phase recommend 3 scenarios"
