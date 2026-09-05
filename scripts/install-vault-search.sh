#!/usr/bin/env bash
# install-vault-search.sh — vault-search MCP server install + Claude config register (Tier 3).
# v2.2.0: vendored source (vendor/vault-search-mcp) + script-root detection + `claude mcp add` registration.
#   - v2.1.1 까지는 github.com/treylom/vault-search-mcp clone 에 의존했으나 해당 레포는 비공개/부재 →
#     신규 설치가 항상 실패했음. 소스를 vendor/ 에 동봉하는 방식으로 전환 (2026-06-10).
#   - Claude Code 는 claude_desktop_config.json 을 읽지 않으므로 `claude mcp add` 를 1차 등록 경로로 사용.
#     (claude_desktop_config.json merge 는 Claude Desktop 사용자용 fallback 으로 유지.)
set -e

# repo root = this script's parent dir (works for ~/.claude/plugins/thiscode, ~/code/thiscode, anywhere)
SCRIPT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

VAULT_DEFAULT="${VAULT:-$HOME/obsidian-ai-vault}"

usage() {
  cat <<EOF >&2
Usage: $0 [--dry-run | --apply | --recommend-only]
  --dry-run         (default) 변경 없이 install 시뮬레이션
  --apply           실제 install (vendored source npm install + build + MCP register)
  --recommend-only  note_count_check 만 (preflight 단계)

Env:
  VAULT                  vault root (default: \$HOME/obsidian-ai-vault — any path works)
  CLAUDE_CONFIG_DIR      Claude Desktop config dir (fallback register; default: \$HOME/.config/claude)
  CLAUDE_DISCODE_HOME    thiscode repo root (default: auto-detected from this script's location)
  CLAUDE_DISCODE_SKIP_BUILD  1 = skip npm install/build (use existing build)
EOF
}

MODE=dry-run
case "${1:-}" in
  --dry-run)        MODE=dry-run ;;
  --apply)          MODE=apply ;;
  --recommend-only) MODE=recommend ;;
  -h|--help)        usage; exit 0 ;;
  "")               MODE=dry-run ;;
  *)                echo "unknown arg: $1" >&2; usage; exit 2 ;;
esac

note_count_check() {
  local vault="${VAULT:-${VAULT_DEFAULT}}"
  if [ -z "$vault" ] || [ ! -d "$vault" ]; then
    echo "[note_count] vault path missing or invalid: $vault" >&2
    return 0
  fi
  local n
  n=$(find "$vault" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
  if [ "${n:-0}" -lt 100 ]; then
    echo "[note_count] warn — currently $n notes, 100+ recommended for vault-search MCP" >&2
    return 0
  fi
  echo "[note_count] $n notes found — OK"
  return 0
}

if [ "$MODE" = "recommend" ]; then
  note_count_check
  exit 0
fi

# preflight (note_count warn only)
note_count_check || true

REPO_DIR="${CLAUDE_DISCODE_HOME:-$SCRIPT_ROOT}/vendor/vault-search-mcp"
SKIP_BUILD="${CLAUDE_DISCODE_SKIP_BUILD:-0}"

# Stage 1: build the vendored MCP source
if [ ! -d "$REPO_DIR" ]; then
  echo "[stage1] vendored source missing: $REPO_DIR" >&2
  echo "         expected vendor/vault-search-mcp inside the thiscode repo." >&2
  echo "         If you installed thiscode elsewhere, set CLAUDE_DISCODE_HOME=<repo root>." >&2
  exit 3
fi
if [ "$MODE" = "apply" ] && [ "$SKIP_BUILD" = "0" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "[stage1] npm missing — install Node.js 18+ first (https://nodejs.org)" >&2
    exit 5
  fi
  echo "[stage1] npm install + build (vendored source: $REPO_DIR)..."
  (cd "$REPO_DIR" && npm install --silent && npm run build --silent)
fi

DIST_JS="$REPO_DIR/dist/index.js"

if [ "$MODE" = "dry-run" ]; then
  echo "[dry-run] would build: $REPO_DIR (npm install + npm run build)"
  if command -v claude >/dev/null 2>&1; then
    echo "[dry-run] would register (Claude Code): claude mcp add vault-search -s user -- node $DIST_JS"
  else
    echo "[dry-run] claude CLI not found — would merge into Claude Desktop config instead"
  fi
  echo "[dry-run] run with --apply to commit"
  exit 0
fi

# Stage 2 (apply): register the MCP server.
# Primary path: Claude Code (`claude mcp add`). Fallback: Claude Desktop config merge.
if command -v claude >/dev/null 2>&1; then
  if claude mcp get vault-search >/dev/null 2>&1; then
    echo "[stage2] vault-search already registered in Claude Code — re-registering with current path"
    claude mcp remove vault-search -s user >/dev/null 2>&1 || true
  fi
  claude mcp add vault-search -s user \
    -e "VAULT_PATH=${VAULT:-$VAULT_DEFAULT}" -- node "$DIST_JS"
  echo "[apply] ✓ vault-search MCP registered via 'claude mcp add' (user scope)"
  echo "[apply] verify: claude mcp list"
else
  CFG="${CLAUDE_CONFIG_DIR:-$HOME/.config/claude}/claude_desktop_config.json"
  if ! command -v jq >/dev/null 2>&1; then
    echo "[stage2] jq missing — install jq first (brew install jq / apt install jq)" >&2
    exit 4
  fi
  mkdir -p "$(dirname "$CFG")"
  [ -f "$CFG" ] || echo '{"mcpServers":{}}' > "$CFG"
  NEW_ENTRY=$(jq -n --arg cmd "node" --arg path "$DIST_JS" --arg vault "${VAULT:-$VAULT_DEFAULT}" \
    '{ command: $cmd, args: [$path], env: { VAULT_PATH: $vault } }')
  TMP=$(mktemp)
  trap 'rm -f "$TMP"' EXIT
  jq --argjson entry "$NEW_ENTRY" '.mcpServers["vault-search"] = $entry' "$CFG" > "$TMP"
  mv "$TMP" "$CFG"
  trap - EXIT
  echo "[apply] ✓ vault-search MCP merged into $CFG (Claude Desktop)"
  echo "[apply] note: Claude Code does NOT read this file — install the claude CLI and re-run for Claude Code."
fi
echo "[apply] restart Claude Code / Claude Desktop to load the new MCP server"
