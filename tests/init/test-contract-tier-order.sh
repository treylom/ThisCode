#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
F="$ROOT/contracts/search-fallback-4tier.md"

# Current km order (GraphRAG → Obsidian CLI → Obsidian MCP → text search) 명시
grep -E '^\| 2 \| Obsidian CLI \|' "$F" >/dev/null || { echo "FAIL: Tier 2 = CLI 누락"; exit 1; }
grep -E '^\| 3 \| Obsidian MCP \|' "$F" >/dev/null || { echo "FAIL: Tier 3 = Obsidian MCP 누락"; exit 1; }

# vault-search is a separate local tool, not the km Tier 3 row.
! grep -E '^\| 3 \| vault-search MCP \|' "$F" >/dev/null || { echo "FAIL: local vault-search mislabeled as km Tier 3"; exit 1; }
! grep -E '^\| 3 \| Obsidian CLI \|' "$F" >/dev/null || { echo "FAIL: v2.0 잔재 Tier 3 = CLI"; exit 1; }

echo "PASS contract tier order"
