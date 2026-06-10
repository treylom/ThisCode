#!/bin/bash
# Stop hook: backup guard for Memory §5 marker/evidence.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
if [ -f "$ROOT/.claude/scripts/memory_s5.py" ]; then
  SCRIPT="$ROOT/.claude/scripts/memory_s5.py"
elif [ -f "$ROOT/scripts/memory_s5.py" ]; then
  SCRIPT="$ROOT/scripts/memory_s5.py"
else
  # VAULT_ROOT = your Obsidian vault path (default kept for the reference deployment)
  SCRIPT="${VAULT_ROOT:-$HOME/obsidian-ai-vault}/.claude/scripts/memory_s5.py"
fi
python3 "$SCRIPT" stop-guard 2>/dev/null || true
exit 0
