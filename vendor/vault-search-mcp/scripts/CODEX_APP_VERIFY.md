# Codex Windows App 수동 검증 가이드

## 사전 조건
- `~/.codex/config.toml` (Windows: `C:\Users\treyl\.codex\config.toml`)에
  `vault-search` MCP가 이미 등록되어 있어야 함 (이미 완료됨).
- WSL 안에서 GraphRAG 서비스가 active:
  ```
  systemctl --user is-active graphrag-serve.service
  ```

## 검증 순서

### 1. 도구 노출 확인
Codex Windows App을 열고 **새 세션**에서 다음 입력:

```
사용 가능한 MCP 도구를 list해줘.
```

**기대 결과**: `vault-search` 서버에서 다음 3개 도구가 노출되어야 함.
- `vault_search`
- `vault_context`
- `vault_graph`

### 2. vault_search 호출 (GraphRAG primary)
```
vault-search MCP의 vault_search 도구를 query="GraphRAG", topK=3 으로 호출하고
결과를 그대로 보여줘.
```

**기대 결과** (예시):
```json
[
  { "title": "GraphRAG-Theory-MOC", "source": "graphrag", "score": 0.043... },
  { "title": "GraphRAG-Theory",     "source": "graphrag", "score": 0.037... },
  { "title": "Level-1-핵심개념-MOC", "source": "graphrag", "score": 0.035... }
]
```

핵심 검증 포인트:
- `"source": "graphrag"` (BM25/vector 폴백이 아닌 GraphRAG 우선)
- `score`는 RRF 가중치 (0.0~0.1 범위)
- 결과는 정렬됨 (score desc)

### 3. vault_context (LLM-ready 컨텍스트)
```
vault_context 도구를 query="옵시디언 워크플로우" 로 호출해줘.
```

**기대 결과**: `context` 필드에 마크다운 형태의 통합 컨텍스트 + `sources` 배열에 노트 슬러그.

### 4. vault_graph (엔티티 그래프)
```
vault_graph 도구를 entity="Anthropic" 으로 호출해줘.
```

**기대 결과**: `matches`, `oneHop`, `twoHop`, `communities` 키 포함된 그래프 응답.

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `node_missing` handshake fail | nvm PATH 누락 | `run-mcp.sh` 사용 (이미 적용됨) |
| `"source": "bm25"`만 나옴 | GraphRAG 다운/잘못된 URL | `systemctl --user status graphrag-serve` 확인 |
| 응답 없이 timeout | GraphRAG 4채널 cold start | `GRAPHRAG_TIMEOUT_MS=30000` 으로 늘림 |
| 도구 목록에 없음 | MCP 등록 누락/오타 | `cat ~/.codex/config.toml` (Windows path) 확인 |

## CLI 측 자동 검증 (참고)
WSL 안에서는 동일 검증을 자동 실행 가능:
```bash
cd /home/tofu/AI/agent-office/vault-search-mcp
./scripts/verify.sh stdio   # JSON-RPC 직접
./scripts/verify.sh http    # StreamableHTTP transport (포트 8401)
./scripts/verify.sh codex   # codex CLI exec (Codex App 아님 — CLI 전용)
```
