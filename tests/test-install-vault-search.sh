#!/usr/bin/env bash
# Test: install-vault-search.sh creates MCP config entry without overwriting other servers.
# Uses CLAUDE_DISCODE_SKIP_BUILD=1 to skip git clone + npm install (heavy steps covered by dogfood T3.2).
set -e

FIXTURE_ROOT=$(mktemp -d)
trap 'rm -rf -- "$FIXTURE_ROOT"' EXIT
mkdir -p "$FIXTURE_ROOT/config" "$FIXTURE_ROOT/bin" "$FIXTURE_ROOT/vault"
cat > "$FIXTURE_ROOT/config/claude_desktop_config.json" <<'JSON'
{ "mcpServers": { "other-mcp": { "command": "node", "args": ["/some/path"] } } }
JSON

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/install-vault-search.sh"

# Force the Desktop fallback without invoking the host Claude CLI.
for fixture_tool in dirname find wc tr mkdir jq mktemp mv rm; do
  ln -s "$(command -v "$fixture_tool")" "$FIXTURE_ROOT/bin/$fixture_tool"
done
run_installer() {
  PATH="$FIXTURE_ROOT/bin" VAULT="$FIXTURE_ROOT/vault" \
    CLAUDE_CONFIG_DIR="$FIXTURE_ROOT/config" CLAUDE_DISCODE_HOME="$REPO_ROOT" \
    CLAUDE_DISCODE_SKIP_BUILD=1 /bin/bash "$SCRIPT" "$@"
}

# Dry-run must select the expected fallback without modifying the config.
run_installer --dry-run | \
  grep -q "would merge into Claude Desktop config" || { echo "FAIL: dry-run output"; exit 1; }
jq -e '.mcpServers."other-mcp" and (.mcpServers | has("vault-search") | not)' \
  "$FIXTURE_ROOT/config/claude_desktop_config.json" >/dev/null

# Apply (build skipped): verify merge into existing config
run_installer --apply >/dev/null

jq -e '.mcpServers."vault-search" and .mcpServers."other-mcp"' \
  "$FIXTURE_ROOT/config/claude_desktop_config.json" >/dev/null \
  || { echo "FAIL: merge"; exit 1; }

echo "PASS"
