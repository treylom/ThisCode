#!/usr/bin/env bash
# km-version.sh — compare thiscode contracts vs vault mirror, warn on drift.
set -e

# repo root = this script's parent dir (works for ~/.claude/plugins/thiscode, ~/code/thiscode, anywhere)
SCRIPT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="${CLAUDE_DISCODE_HOME:-$SCRIPT_ROOT}/contracts"
VAULT_DIR="${CLAUDE_DISCODE_VAULT:-$HOME/obsidian-ai-vault}/.claude/reference/contracts"

if [ ! -d "$PLUGIN_DIR" ]; then
  echo "plugin contracts dir missing: $PLUGIN_DIR" >&2
  exit 1
fi

if [ ! -d "$VAULT_DIR" ]; then
  echo "vault mirror missing: $VAULT_DIR — run /thiscode:km-bootstrap" >&2
  exit 2
fi

drift=0
for f in "$PLUGIN_DIR"/*.md; do
  name=$(basename "$f")
  if [ ! -f "$VAULT_DIR/$name" ]; then
    echo "WARNING: drift — $name missing in vault"
    drift=1
    continue
  fi
  pv=$(grep -E '^version:' "$f" | head -1 | awk '{print $2}')
  vv=$(grep -E '^version:' "$VAULT_DIR/$name" | head -1 | awk '{print $2}')
  if [ "$pv" = "$vv" ]; then
    echo "ok: $pv == $vv ($name)"
  else
    echo "WARNING: drift — $name plugin=$pv vault=$vv"
    drift=1
  fi
done

exit $drift
