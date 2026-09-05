---
contract: search-fallback-4tier
version: 0.3.0
date: 2026-09-05
---

# 4-Tier Search Fallback Contract

This is a compatibility pointer for the external km plugin's `/km:search`
dispatcher. It records the current km order; it does not add a command or make
ThisCode a knowledge-management or search provider. A vault-local
`.claude/commands/search.md` may delegate to the km dispatcher.

The km plugin owns fallback execution and configuration. Its current order is
GraphRAG, Obsidian CLI, Obsidian MCP, then text search. Knowledge workflows
belong to `/km:knowledge-manager`, and km integrations are configured through
`/km:setup`.

ThisCode provides optional local-engine installers in `scripts/install-*.sh`.
They prepare local tools only. In particular, `install-vault-search.sh`
registers a separate local MCP tool; that tool is not the km plugin's Tier 3
Obsidian MCP stage and is not a substitute for it.

> Weight params removed 2026-07-29 (contract v0.2.0): hard-coded client
> weights silently overrode the server's launch-config weights. This historical
> note does not add a current km request requirement.

## Current km order (pointer only)

The km plugin's current search documentation names these stages in this
order. It owns the request shape, availability checks, timeouts, response
decoding, and failure behavior; this compatibility pointer does not prescribe
those details.

| Tier | Current km stage |
|---|---|
| 1 | GraphRAG |
| 2 | Obsidian CLI |
| 3 | Obsidian MCP |
| 4 | Text search (`ripgrep` / `grep`) |

## Local-engine examples (not km protocol)

The following examples describe optional ThisCode local tools only. They are
not normative `/km:search` requests or responses; the km plugin may invoke its
own integrations differently.

### ThisCode local GraphRAG example

```bash
QUERY_ENCODED=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$QUERY")
curl -s "http://127.0.0.1:8400/api/search?q=${QUERY_ENCODED}&top_k=${TOP_K}&mode=hybrid" --connect-timeout 3
```

Response: `{ "results": [{ "source_note": "<path>", "score": <float>, "snippet": "..." }, ...] }`

### ThisCode local Obsidian CLI example

```bash
/Applications/Obsidian.app/Contents/MacOS/obsidian-cli search query="$QUERY" format=json limit=1000
```

Response: JSON array of vault-relative paths. Obsidian CLI is full-text, but has weak/no relevance ranking; use it as the required safety-net fallback after GraphRAG, not as primary semantic recall.

### Separate ThisCode local vault-search MCP (not km Tier 3)

The optional bundled `vault-search-mcp` server is installed by
`scripts/install-vault-search.sh`. It is a separate local tool, not one of the
four km stages above. Its registered API is documented here so callers do not
confuse its protocol with the km plugin's Obsidian MCP integration.

The server registers `vault_search` with a required `query` string and an
optional numeric `topK`:

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
The local tool's `vault_search` response contains ranked snippets and scores.
The server does not register a `list_notes` tool. These local API details do
not change the km fallback order.

### ThisCode local text-search example

```bash
rg --type md --json --max-count 5 "$QUERY" "$VAULT_ROOT" 2>/dev/null || \
  grep -r -l --include="*.md" "$QUERY" "$VAULT_ROOT"
```

Response: file list + matched lines. A ThisCode local runner may include a
`[Tier 4: 텍스트 검색 결과입니다]` notice; the km plugin owns its own output.

## Failure mode

The km plugin owns failure handling. The following is a historical example of
the old local-tool guidance, not a required km response:
```
4-Tier search 전부 실패 — km 설정은 `/km:setup`에서 구성한 뒤 `/km:search`를
다시 실행하십시오. ThisCode의 `scripts/install-*.sh`는 선택적 로컬 도구를
설치하지만 km 계약 미러를 만들거나 km 폴백을 실행하지 않습니다.
```

## MOC routing

MOC ranking is not defined by this compatibility pointer. Follow the km
plugin's current search documentation for any result-ordering behavior.

Historical benchmark records may retain numeric labels for local engines.
Those labels describe the old benchmark fixtures only; they are not the
current km tier order.
