#!/usr/bin/env bash
# vault-search-mcp 다중 환경 검증 스크립트.
#
# 사용:
#   ./scripts/verify.sh              # 모든 검증 (stdio + http + codex)
#   ./scripts/verify.sh stdio        # stdio JSON-RPC만
#   ./scripts/verify.sh http         # HTTP transport만 (서버 자동 기동)
#   ./scripts/verify.sh codex        # codex exec 호출만
#
# 환경변수:
#   VAULT_PATH               vault 경로 (default: /home/tofu/AI/AI_Second_Brain)
#   GRAPHRAG_API_URL         GraphRAG 서버 (default: http://127.0.0.1:8400)
#   MCP_HTTP_PORT            HTTP 검증 포트 (default: 8401)
#   MCP_AUTH_TOKEN           HTTP 인증 토큰 (default: verify-test-token)
#   QUERY                    테스트 쿼리 (default: GraphRAG)

set -u
set -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_INDEX="$REPO_ROOT/dist/index.js"
DIST_HTTP="$REPO_ROOT/dist/http.js"

VAULT_PATH="${VAULT_PATH:-/home/tofu/AI/AI_Second_Brain}"
GRAPHRAG_API_URL="${GRAPHRAG_API_URL:-http://127.0.0.1:8400}"
MCP_HTTP_PORT="${MCP_HTTP_PORT:-8401}"
MCP_AUTH_TOKEN="${MCP_AUTH_TOKEN:-verify-test-token}"
QUERY="${QUERY:-GraphRAG}"

PASS=0
FAIL=0

ok()   { echo "  ✅ $*"; PASS=$((PASS+1)); }
fail() { echo "  ❌ $*"; FAIL=$((FAIL+1)); }
note() { echo "  ℹ️  $*"; }

require_file() {
  if [ ! -f "$1" ]; then
    echo "❌ missing: $1 — run 'npm run build' first" >&2
    exit 2
  fi
}

verify_stdio() {
  echo "=== [stdio] JSON-RPC handshake + tools/call ==="
  require_file "$DIST_INDEX"

  local out
  out="$(
    (
      echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify","version":"0.0.1"}}}'
      sleep 0.3
      echo '{"jsonrpc":"2.0","method":"notifications/initialized"}'
      sleep 0.3
      echo "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"vault_search\",\"arguments\":{\"query\":\"$QUERY\",\"topK\":3}}}"
      sleep 5
    ) | VAULT_PATH="$VAULT_PATH" GRAPHRAG_API_URL="$GRAPHRAG_API_URL" GRAPHRAG_MODE=primary node "$DIST_INDEX" 2>/dev/null
  )"

  if echo "$out" | grep -q '"protocolVersion":"2024-11-05"'; then
    ok "initialize handshake"
  else
    fail "initialize handshake"
    return 1
  fi

  if echo "$out" | grep -q '"name":"vault-search-mcp"'; then
    ok "server identity"
  else
    fail "server identity"
  fi

  local source
  source="$(echo "$out" | grep -oE '\\"source\\": \\"(graphrag|bm25|vector|both)\\"|"source": "(graphrag|bm25|vector|both)"' | head -1)"
  if [ -n "$source" ]; then
    ok "vault_search tool returned results ($source)"
  else
    fail "vault_search tool returned no parseable results"
    note "raw output snippet: $(echo "$out" | tail -c 300)"
  fi
}

verify_http() {
  echo "=== [http] StreamableHTTP transport (port $MCP_HTTP_PORT) ==="
  require_file "$DIST_HTTP"

  if lsof -ti ":$MCP_HTTP_PORT" >/dev/null 2>&1; then
    note "port $MCP_HTTP_PORT already in use — using existing server"
  else
    note "starting test server in background"
    VAULT_PATH="$VAULT_PATH" GRAPHRAG_API_URL="$GRAPHRAG_API_URL" \
      MCP_HTTP_PORT="$MCP_HTTP_PORT" MCP_AUTH_TOKEN="$MCP_AUTH_TOKEN" \
      node "$DIST_HTTP" >/tmp/verify-http.log 2>&1 &
    local pid=$!
    trap "kill $pid 2>/dev/null; trap - EXIT" EXIT
    sleep 1.5
  fi

  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$MCP_HTTP_PORT/healthz")"
  if [ "$code" = "200" ]; then ok "/healthz returns 200"
  else fail "/healthz returned HTTP $code"
  fi

  code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$MCP_HTTP_PORT/mcp" \
    -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"v","version":"0"}}}')"
  if [ "$code" = "401" ]; then ok "unauth POST /mcp returns 401"
  else fail "unauth POST /mcp returned HTTP $code (expected 401)"
  fi

  local headers session_id
  headers="$(curl -s -i -X POST "http://127.0.0.1:$MCP_HTTP_PORT/mcp" \
    -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
    -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"v","version":"0"}}}')"
  session_id="$(echo "$headers" | grep -i '^mcp-session-id:' | awk '{print $2}' | tr -d '\r\n')"

  if [ -n "$session_id" ]; then ok "auth init returns session-id ($session_id)"
  else fail "auth init missing session-id"; return 1
  fi

  curl -s -X POST "http://127.0.0.1:$MCP_HTTP_PORT/mcp" \
    -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
    -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
    -H "mcp-session-id: $session_id" \
    -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null

  local body
  body="$(curl -s -X POST "http://127.0.0.1:$MCP_HTTP_PORT/mcp" \
    -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
    -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
    -H "mcp-session-id: $session_id" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"vault_search\",\"arguments\":{\"query\":\"$QUERY\",\"topK\":2}}}")"

  if echo "$body" | grep -qE '\\"source\\": \\"(graphrag|bm25|vector|both)\\"|"source": ?"(graphrag|bm25|vector|both)"'; then
    ok "tools/call vault_search returned results"
  else
    fail "tools/call vault_search returned no parseable results"
    note "body: $(echo "$body" | head -c 400)"
  fi
}

verify_codex() {
  echo "=== [codex] codex exec → vault_search MCP 호출 ==="

  if ! command -v codex >/dev/null 2>&1; then
    fail "codex CLI not in PATH"
    return 1
  fi

  if ! codex mcp list 2>/dev/null | grep -q '^vault-search'; then
    fail "vault-search not registered in 'codex mcp list'"
    note "register: codex mcp add vault-search -- node $DIST_INDEX --env VAULT_PATH=$VAULT_PATH"
    return 1
  fi
  ok "vault-search registered in codex CLI"

  note "running: codex exec --sandbox read-only \"vault_search '$QUERY' top 2\""
  local result
  result="$(codex exec --skip-git-repo-check --sandbox read-only \
    --model gpt-5.5 \
    "vault-search MCP의 vault_search 도구를 query=\"$QUERY\", topK=2로 호출하고, 결과의 첫 항목 title을 한 줄로만 출력해주세요. 다른 설명 일절 없이 title만." 2>&1 | tail -10)"

  if echo "$result" | grep -qiE 'graphrag|moc|theory|level'; then
    ok "codex exec successfully invoked vault_search ($(echo "$result" | tail -1 | head -c 80)...)"
  else
    fail "codex exec did not return expected vault_search result"
    note "result (last 5 lines):"
    echo "$result" | tail -5 | sed 's/^/      /'
  fi
}

case "${1:-all}" in
  stdio) verify_stdio ;;
  http)  verify_http ;;
  codex) verify_codex ;;
  all)   verify_stdio; echo; verify_http; echo; verify_codex ;;
  *)
    echo "usage: $0 {all|stdio|http|codex}" >&2
    exit 2
    ;;
esac

echo
echo "── 결과: PASS=$PASS FAIL=$FAIL ──"
[ "$FAIL" -eq 0 ]
