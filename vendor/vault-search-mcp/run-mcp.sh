#!/bin/bash
# run-mcp.sh — vault-search MCP launcher (stdio).
# wsl.exe non-interactive PATH lacks nvm — load it explicitly, then exec node.
# CRITICAL: all setup output goes to stderr. stdout is reserved for MCP JSON-RPC.
# Set VAULT_PATH (your Obsidian vault root) before running, or pass it via MCP config env.
{
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" --no-use
  NODE_BIN="$(command -v node)"
  if [ -z "$NODE_BIN" ]; then
    echo "[run-mcp] node not found — install Node.js 18+ (https://nodejs.org)" >&2
    exit 1
  fi
  export VAULT_PATH="${VAULT_PATH:-$HOME/your-vault}"
  export GRAPHRAG_DB_PATH="${GRAPHRAG_DB_PATH:-}"
  export GRAPHRAG_API_URL="${GRAPHRAG_API_URL:-http://127.0.0.1:8400}"
  export GRAPHRAG_MODE="${GRAPHRAG_MODE:-primary}"
  export GRAPHRAG_TIMEOUT_MS="${GRAPHRAG_TIMEOUT_MS:-15000}"
} >&2
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$NODE_BIN" "$SCRIPT_DIR/dist/index.js" "$@"
