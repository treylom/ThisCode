# vault-search-mcp

Personal Obsidian vault search MCP server with GraphRAG hybrid retrieval, WorkOS OAuth authentication, and ChatGPT/Claude/Codex compatibility.

## Tools

| Tool | Purpose | Required for |
|---|---|---|
| `search` | ChatGPT spec — `{query} → {results:[{id,title,url}]}` | ChatGPT custom connector |
| `fetch` | ChatGPT spec — `{id} → {id,title,text,url,metadata}` | ChatGPT custom connector |
| `vault_search` | Hybrid BM25 + Schift vector + GraphRAG primary | Codex, Claude Code |
| `vault_context` | LLM-ready context with linked notes + graph | Codex, Claude Code |
| `vault_graph` | GraphRAG entity neighborhood + community | Codex, Claude Code |

## Documentation

- **[ChatGPT 셋업 가이드](docs/SETUP-CHATGPT.md)** — WorkOS AuthKit + ngrok 무료 dev domain. **권장 path** (검증됨)
- [`CHATGPT_CONNECTOR.md`](CHATGPT_CONNECTOR.md) — Legacy cloudflared + Bearer 모드 (deprecated, 참고용)

## Stack

- TypeScript + Express + `@modelcontextprotocol/sdk`
- `jose` for JWT verification (WorkOS AuthKit)
- `better-sqlite3` for GraphRAG SQLite read-only access
- `@schift-io/sdk` for hybrid vector search (optional)
- StreamableHTTP transport (ChatGPT/Codex App) + stdio (Codex CLI / Claude Code)

## Quick Start

See [`docs/SETUP-CHATGPT.md`](docs/SETUP-CHATGPT.md). 30분 내 ChatGPT Business workspace에 등록 가능.

## Verification

Built-in verification scripts:

```bash
./scripts/verify.sh stdio        # JSON-RPC handshake via stdio
./scripts/verify.sh http         # Local HTTP transport
```

External (ngrok) verification:

```bash
DOMAIN=https://YOUR-DEV-DOMAIN.ngrok-free.dev
curl -sS $DOMAIN/healthz
curl -sS $DOMAIN/.well-known/oauth-protected-resource/mcp
curl -sS $DOMAIN/.well-known/oauth-authorization-server/mcp  # /mcp suffix required by ChatGPT
```

## License

Personal use. No license granted.
