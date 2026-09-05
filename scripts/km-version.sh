#!/usr/bin/env bash
# km-version.sh — compare ThisCode contract versions with the vault mirror.
set -euo pipefail

# repo root = this script's parent dir (works for ~/.claude/plugins/thiscode, ~/code/thiscode, anywhere)
SCRIPT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="${CLAUDE_DISCODE_HOME:-$SCRIPT_ROOT}/contracts"
VAULT_DIR="${CLAUDE_DISCODE_VAULT:-$HOME/obsidian-ai-vault}/.claude/reference/contracts"

if [ ! -d "$PLUGIN_DIR" ]; then
  echo "plugin contracts dir missing: $PLUGIN_DIR" >&2
  exit 1
fi

if [ ! -d "$VAULT_DIR" ]; then
  echo "vault mirror missing: $VAULT_DIR — populate it from $PLUGIN_DIR before rerunning; no installer creates contract mirrors" >&2
  exit 2
fi

drift=0
found_contract=0

# Contract versions live in YAML frontmatter and use the repository's simple
# MAJOR.MINOR.PATCH format. Rejecting malformed metadata is important:
# comparing two empty strings would otherwise report a false match.
read_contract_version() {
  local file="$1"
  awk '
    BEGIN { in_front=0; ended=0; count=0; invalid=0; version="" }
    {
      line=$0
      sub(/\r$/, "", line)
    }
    NR == 1 {
      if (line != "---") { invalid=1; exit }
      in_front=1
      next
    }
    in_front && line == "---" {
      ended=1
      in_front=0
      next
    }
    in_front && line ~ /^version:/ {
      count++
      value=line
      sub(/^version:[[:space:]]*/, "", value)
      gsub(/[[:space:]]+$/, "", value)
      if (value !~ /^[0-9]+\.[0-9]+\.[0-9]+$/) invalid=1
      version=value
    }
    END {
      if (!ended || count != 1 || invalid) exit 1
      print version
    }
  ' "$file"
}

for f in "$PLUGIN_DIR"/*.md; do
  [ -f "$f" ] || continue
  found_contract=1
  name=$(basename "$f")

  if pv=$(read_contract_version "$f"); then
    :
  else
    echo "ERROR: invalid or missing version metadata — plugin contract $name" >&2
    drift=1
    continue
  fi

  if [ ! -f "$VAULT_DIR/$name" ]; then
    echo "WARNING: drift — $name missing in vault"
    drift=1
    continue
  fi

  if vv=$(read_contract_version "$VAULT_DIR/$name"); then
    :
  else
    echo "ERROR: invalid or missing version metadata — vault contract $name" >&2
    drift=1
    continue
  fi

  if [ "$pv" = "$vv" ]; then
    echo "ok: $pv == $vv ($name)"
  else
    echo "WARNING: drift — $name plugin=$pv vault=$vv"
    drift=1
  fi
done

if [ "$found_contract" -eq 0 ]; then
  echo "ERROR: no contract files found: $PLUGIN_DIR" >&2
  exit 1
fi

exit $drift
