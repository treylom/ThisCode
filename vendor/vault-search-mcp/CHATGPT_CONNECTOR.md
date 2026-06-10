# ChatGPT Custom Connector 등록 가이드

## 현재 상태 (2026-04-27)
- **HTTP MCP 서버**: `vault-search-http.service` (systemd user, 포트 8401, 자동 재시작)
- **터널**: `cloudflared-vault-search.service` (quick tunnel, 임시 URL)
- **인증**: Bearer 토큰 (64-byte hex), `~/.config/vault-search-mcp/env`에 저장 (chmod 600)

## 토큰 / URL 조회
```bash
# 토큰 (이 값을 ChatGPT에 입력)
grep "^MCP_AUTH_TOKEN=" ~/.config/vault-search-mcp/env | cut -d= -f2

# 터널 URL (quick tunnel은 재시작 시마다 변경됨!)
grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' ~/.cache/cloudflared-vault-search.log | tail -1
```

## ChatGPT 등록 절차

### 1. Custom Connector 메뉴 진입
- ChatGPT (Plus/Team/Enterprise) → **Settings** → **Connectors** (베타 활성 필요할 수 있음)
- 또는 직접: https://chatgpt.com/g/g-connectors (UI 변경 가능)
- **Add Connector** → **MCP Server**

### 2. 입력값
| 필드 | 값 |
|------|---|
| Name | `vault-search` (또는 `My Vault`) |
| URL | `https://<현재-터널-URL>/mcp` |
| Auth Type | `Bearer` |
| Token | (`MCP_AUTH_TOKEN` 값 그대로 붙여넣기) |
| Allowed Tools | `vault_search`, `vault_context`, `vault_graph` (전부 체크) |

### 3. 검증 (ChatGPT 안에서)
새 대화에서 입력:
```
vault-search 커넥터의 vault_search 도구로 query="GraphRAG", topK=3 호출하고
결과 그대로 보여줘.
```

**기대**: `"source": "graphrag"` 결과 3개 + 동일 score 분포 (Codex App 검증 결과와 동일).

## Quick Tunnel 한계 + 영구화 옵션

| 옵션 | 가용성 | 영구 URL | 설정 비용 |
|------|--------|----------|-----------|
| **Quick Tunnel (현재)** | 즉시 | ❌ 재시작마다 변경 | 0 |
| **Named Tunnel + DNS** | 1회 설정 | ✅ `vault.<domain>` | Cloudflare 계정 + 도메인 필요 |
| **Cloudflare Zero Trust + Access** | 1회 설정 | ✅ + Google/Email 인증 | 계정 + 도메인 + Access 정책 |

영구화 요청 시 알려주세요. Named Tunnel 마이그레이션 단계는:
1. `cloudflared tunnel login` (브라우저 인증)
2. `cloudflared tunnel create vault-search`
3. `cloudflared tunnel route dns vault-search vault.<your-domain>`
4. `~/.cloudflared/config.yml` 작성 + systemd 서비스 수정

## 운영 명령

```bash
# 상태 확인
systemctl --user status vault-search-http.service cloudflared-vault-search.service

# 로그
tail -f ~/.cache/vault-search-http.log
tail -f ~/.cache/cloudflared-vault-search.log

# 토큰 회전
NEW_TOKEN=$(openssl rand -hex 32)
sed -i "s|^MCP_AUTH_TOKEN=.*|MCP_AUTH_TOKEN=${NEW_TOKEN}|" ~/.config/vault-search-mcp/env
systemctl --user restart vault-search-http.service
echo "$NEW_TOKEN"  # ChatGPT 측 토큰 갱신 필요

# 외부 노출 즉시 중단
systemctl --user stop cloudflared-vault-search.service

# 완전 비활성화
systemctl --user disable --now vault-search-http.service cloudflared-vault-search.service
```

## 보안 노트
- `~/.config/vault-search-mcp/env`는 chmod 600 (본인만 읽기). git 추적 안 됨.
- `MCP_HTTP_HOST=127.0.0.1` 설정 — HTTP 서버 자체는 외부 직접 노출 X. cloudflared만 외부 진입점.
- Quick tunnel URL은 **공개 인터넷에서 추측 불가능한 무작위 서브도메인**이지만, 토큰 누출 시 즉시 회전 필수.
- Origin 화이트리스트 필요 시 `MCP_ALLOWED_ORIGINS=https://chatgpt.com,https://chat.openai.com`을 env에 추가 후 재시작.
