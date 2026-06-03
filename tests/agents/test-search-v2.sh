#!/usr/bin/env bash
set -e
F=$HOME/code/ThisCode/.agents/search.yaml
grep -q "Tier 2 Obsidian CLI" "$F" || { echo "FAIL: search description Tier 2 = CLI"; exit 1; }
grep -q "Tier 3 vault-search MCP" "$F" || { echo "FAIL: search description Tier 3 = MCP"; exit 1; }
echo "PASS search v2.1"
