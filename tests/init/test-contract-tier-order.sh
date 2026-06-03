#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
F="$ROOT/contracts/search-fallback-4tier.md"

# v2.1 순서 (GraphRAG → Obsidian CLI → vault-search MCP → ripgrep) 명시
grep -E '^\| 2 \| Obsidian CLI \|' "$F" >/dev/null || { echo "FAIL: Tier 2 = CLI 누락"; exit 1; }
grep -E '^\| 3 \| vault-search MCP \|' "$F" >/dev/null || { echo "FAIL: Tier 3 = MCP 누락"; exit 1; }

# v2.0 잔재 (Tier 2 MCP / Tier 3 CLI) 없어야
! grep -E '^\| 2 \| vault-search MCP \|' "$F" >/dev/null || { echo "FAIL: v2.0 잔재 Tier 2 = MCP"; exit 1; }
! grep -E '^\| 3 \| Obsidian CLI \|' "$F" >/dev/null || { echo "FAIL: v2.0 잔재 Tier 3 = CLI"; exit 1; }

echo "PASS contract tier order v2.1"
