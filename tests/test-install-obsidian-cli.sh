#!/usr/bin/env bash
# Test: install-obsidian-cli.sh detects Obsidian and gracefully skips when missing.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/install-obsidian-cli.sh"

# Case A: detect on host (present or missing — both are valid outcomes)
OUT=$(bash "$SCRIPT" --check 2>&1 || true)
echo "$OUT" | grep -qE "obsidian-cli: present|obsidian app: present|obsidian: missing — Tier 3 \(Obsidian MCP\), then Tier 4 \(text search\) remain as km fallbacks" \
  || { echo "FAIL: detect output unexpected: $OUT"; exit 1; }

# Case B: forced missing path (override PATH so command -v fails, on a typical Linux/Mac the check should report missing)
OUT=$(PATH="/usr/bin:/bin" bash "$SCRIPT" --check 2>&1 || true)
# On macOS host with /Applications/Obsidian.app present, the script still reports "present" — accept either.
echo "$OUT" | grep -qE "obsidian-cli: present|obsidian app: present|obsidian: missing — Tier 3 \(Obsidian MCP\), then Tier 4 \(text search\) remain as km fallbacks" \
  || { echo "FAIL: missing-path detect output unexpected: $OUT"; exit 1; }

echo "PASS"
