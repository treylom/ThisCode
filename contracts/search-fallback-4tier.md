---
contract: search-fallback-4tier
version: 0.2.0
date: 2026-07-29
---

# 4-Tier Search Fallback Contract

The km plugin's `/km:search` dispatcher MUST follow this Tier order and
interface. A vault-local `.claude/commands/search.md` may delegate to that
dispatcher; this contract does not make it a ThisCode-provided search command.

ThisCode provides the optional local search-tool installers in
`scripts/install-*.sh` (including ripgrep, Obsidian CLI, vault-search MCP, and
GraphRAG). Those installers prepare engines only; the km plugin owns fallback
execution and km configuration. Knowledge workflows belong to
`/km:knowledge-manager`.

> Weight params removed 2026-07-29 (contract v0.2.0): hard-coded client weights silently overrode the server's launch-config weights. Clients MUST NOT pass channel weights.

## Tier Order (fixed — drift forbidden)

| Tier | Engine | Trigger Check | Timeout | Failure → |
|---|---|---|---|---|
| 1 | GraphRAG FastAPI | `curl --connect-timeout 3 http://127.0.0.1:8400/health` returns 200 | 3s | Tier 2 |
| 2 | Obsidian CLI | `obsidian-cli version` exits 0 (vault root resolvable) | 2s | Tier 3 |
| 3 | vault-search MCP | `mcp__vault-search__vault_search({ "query": "$QUERY", "topK": N })` succeeds and `content[0].text` contains parseable JSON | 5s | Tier 4 |
| 4 | ripgrep / grep | `rg --version` exits 0 (or `grep` fallback) | 10s | Final fail |

## Tier 1 — GraphRAG call

```bash
QUERY_ENCODED=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$QUERY")
curl -s "http://127.0.0.1:8400/api/search?q=${QUERY_ENCODED}&top_k=${TOP_K}&mode=hybrid" --connect-timeout 3
```

Response: `{ "results": [{ "source_note": "<path>", "score": <float>, "snippet": "..." }, ...] }`

## Tier 2 — Obsidian CLI call

```bash
/Applications/Obsidian.app/Contents/MacOS/obsidian-cli search query="$QUERY" format=json limit=1000
```

Response: JSON array of vault-relative paths. Obsidian CLI is full-text, but has weak/no relevance ranking; use it as the required safety-net fallback after GraphRAG, not as primary semantic recall.

## Tier 3 — vault-search MCP call

The bundled `vault-search-mcp` server registers `vault_search` with a required
`query` string and an optional numeric `topK`.

```
mcp__vault-search__vault_search({ "query": "$QUERY", "topK": N })
```

The MCP response is a `CallToolResult`; its first text content block is an
encoded JSON string. Parse `content[0].text` before reading the ranked results:

```json
{
  "_instructions": "...",
  "query": "...",
  "results": [
    { "title": "...", "slug": "...", "snippet": "...", "score": 0.0, "source": "bm25" }
  ]
}
```

The same server also exposes the compatibility tool
`mcp__vault-search__search({ "query": "$QUERY" })`; its encoded JSON payload
is `{ "results": [{ "id": "...", "title": "...", "url": "..." }] }`.
The fallback uses `vault_search` because it returns ranked snippets and scores.

## Tier 4 — ripgrep fallback

```bash
rg --type md --json --max-count 5 "$QUERY" "$VAULT_ROOT" 2>/dev/null || \
  grep -r -l --include="*.md" "$QUERY" "$VAULT_ROOT"
```

Response: file list + matched lines. Output MUST include `[Tier 4: 텍스트 검색 결과입니다]` notice.

## Failure mode

If all 4 Tiers fail, output:
```
4-Tier search 전부 실패 — 로컬 검색 도구는 ThisCode의 `scripts/install-*.sh`로
설치하고, km 설정은 `/km:setup`에서 구성한 뒤 `/km:search`를 다시 실행
```

## MOC priority routing

Both implementations MUST apply MOC priority: if any result note has `type: MOC` (frontmatter) or `-MOC` suffix in filename, surface top-3 MOCs above atomic notes.
