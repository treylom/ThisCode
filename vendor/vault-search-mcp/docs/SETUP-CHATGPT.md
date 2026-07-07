# vault-search-mcp × ChatGPT 커스텀 커넥터 셋업 가이드

> **대상**: 개인/팀 vault(또는 임의 데이터)를 ChatGPT에 OAuth로 안전하게 연결하려는 개발자
> **검증 환경**: WSL Ubuntu, Node 24, Express + TypeScript MCP SDK 1.15.0, ChatGPT Business plan
> **최종 업데이트**: 2026-04-27
> **참고 리서치**: 내부 딥리서치 리포트 (32 sources, A+B 91% — 번들 미포함)

---

## 0. 핵심 요약 (TL;DR)

ChatGPT custom MCP connector는 **검증되지 않은 호스팅 + OAuth 구현 함정** 때문에 silent fail이 자주 발생합니다. 본 가이드는 다음 stack으로 **검증된 path**를 제공합니다:

```
[로컬 vault + GraphRAG SQLite + filesystem]
        ↓
[Express + TypeScript MCP SDK + WorkOS AuthKit JWT 검증]
        ↓
[ngrok 무료 dev domain]
        ↓
[ChatGPT Business workspace custom connector]
```

**기존 시도가 실패하는 가장 흔한 원인 5개**:

1. `*.trycloudflare.com` 도메인 → ChatGPT 백엔드가 silent reject ([OpenAI Community 다수 보고](https://community.openai.com/t/error-creating-connector-request-timeout-for-public-https-mcp-server-cloudflare-tunnel/1367105))
2. `/.well-known/oauth-authorization-server/mcp` (suffix 포함) 미구현 → ChatGPT만 거부 ([resolved thread](https://community.openai.com/t/resolved-trouble-with-chatgpt-connector-oauth-detailed/1359112))
3. `search` + `fetch` tool 이름 정확히 매칭 안 됨 → "이 MCP 서버가 가이드라인 위반" 오류
4. WorkOS DCR 기본값 `client_secret_basic` ↔ ChatGPT public client(`none`) 충돌
5. CORS preflight `OPTIONS` 401 응답 → 브라우저-측 클라이언트 차단

본 가이드는 위 5개를 모두 우회한 셋업입니다.

---

## 1. 사전 요구사항

| 항목 | 비고 |
|---|---|
| **WSL Ubuntu (또는 Linux/macOS)** | 본 문서는 WSL 기준. systemd user services 사용 |
| **Node.js 20+** | TypeScript MCP SDK 요구사항 |
| **vault-search-mcp 코드** | 본 레포 — `pnpm install` 또는 `npm install` |
| **ChatGPT 계정** | Plus/Pro/Business/Enterprise/Edu (Business 권장 — Developer Mode 안정) |
| **WorkOS 계정** | 무료 (1M MAU) — `https://workos.com/signup` |
| **ngrok 계정** | 무료 (1 dev domain 자동 할당) — `https://ngrok.com/signup` |

**도메인은 필요 없음**. ngrok 무료 dev domain (`xxx.ngrok-free.dev`)으로 충분.

---

## 2. WorkOS AuthKit 셋업 (10분)

### 2.1 가입 + AuthKit Domain 확인

1. [https://workos.com/signup](https://workos.com/signup) — Google 또는 이메일 가입 (무료, 카드 등록 불필요)
2. 가입 직후 **Overview** 페이지 표시
3. 좌측 사이드바 **Domains** 클릭
4. **AuthKit Domain** 항목에서 자동 생성된 URL 복사
   - 예: `https://abundant-cloud-12345-staging.authkit.app`
   - 또는 hostname-only 형식 `abundant-cloud-12345-staging.authkit.app` (둘 다 OK)

### 2.2 MCP Auth 활성화 (CIMD + DCR)

1. 좌측 사이드바 **Connect** → **Configuration** 진입
2. **MCP Auth** 섹션 찾기
3. 다음 두 토글 모두 **On**:
   - ☑ **Client ID Metadata Document (CIMD)**
   - ☑ **Dynamic Client Registration (DCR)**
4. **Save**

> 메뉴가 보이지 않으면: 좌측 **Authentication** → **Configuration**, 또는 **Developer** 섹션 확인. UI는 자주 바뀌지만 **"MCP Auth"** 라벨이 핵심.

### 2.3 OAuth Application 생성 + Redirect URIs

1. **Connect** → **Applications** → **+ Create Application**
2. **OAuth** 선택 (M2M 아님 — 사용자 로그인 기반)
3. 이름: `vault-search-mcp` 또는 자유 입력
4. 생성 후 **Redirects** 탭 진입
5. 다음 URI 추가 (**둘 다 등록**, 와일드카드 가능 시):
   ```
   https://chatgpt.com/connector_platform_oauth_redirect
   https://chatgpt.com/connector/oauth/*
   ```

> 와일드카드 미지원 환경이면 ChatGPT가 첫 등록 시 발급한 동적 redirect URI를 에러 메시지에서 복사해서 추가.

### 2.4 (선택) DCR 직접 검증

WorkOS staging이 ChatGPT용 client를 정상 발급하는지 검증:

```bash
curl -sS -X POST https://YOUR-AUTHKIT-DOMAIN.authkit.app/oauth2/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name":"chatgpt-mcp-test",
    "redirect_uris":["https://chatgpt.com/connector_platform_oauth_redirect"],
    "grant_types":["authorization_code","refresh_token"],
    "response_types":["code"],
    "token_endpoint_auth_method":"none",
    "scope":"openid profile email"
  }' | python3 -m json.tool
```

기대 결과: HTTP 201 + `client_id` 발급.

---

## 3. ngrok 셋업 (5분)

### 3.1 가입 + authtoken / dev domain 받기

1. [https://ngrok.com/signup](https://ngrok.com/signup) — 이메일/Google 가입 (무료)
2. 가입 직후 OS 선택 화면이 나오면 **Linux** 선택 (WSL이면 무조건 Linux)
   - **Microsoft Store / Windows installer 무시**
3. 직접 URL `https://dashboard.ngrok.com/get-started/your-authtoken` → **authtoken 복사**
4. 직접 URL `https://dashboard.ngrok.com/domains` → 자동 할당된 dev domain 확인
   - 형식: `xxx-yyy-zzz.ngrok-free.app` 또는 `your-dev-domain.ngrok-free.dev`
   - 미할당 시 **+ New Domain** 또는 **Reserve Domain** 클릭

### 3.2 ngrok 설치 (sudo 없이 binary)

```bash
cd /tmp
curl -sSLO https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar -xzf ngrok-v3-stable-linux-amd64.tgz
mkdir -p ~/.local/bin
mv ngrok ~/.local/bin/ngrok
chmod +x ~/.local/bin/ngrok
~/.local/bin/ngrok version  # 3.38.0+ 표시되면 OK
```

> sudo 권한 있으면 `sudo apt install ngrok` (apt repo 추가 후) 사용 가능. 본 가이드는 sudo 없는 무권한 설치 기준.

### 3.3 authtoken 등록

```bash
~/.local/bin/ngrok config add-authtoken YOUR_AUTHTOKEN
```

성공 시 `~/.config/ngrok/ngrok.yml` 자동 생성.

---

## 4. vault-search-mcp 빌드 + 환경 변수 (5분)

### 4.1 의존성 설치 + 빌드

```bash
cd /path/to/vault-search-mcp
npm install
npm run build  # tsc → dist/ 생성
```

### 4.2 환경 변수 파일 작성

`~/.config/vault-search-mcp/env` 작성 (chmod 600):

```bash
mkdir -p ~/.config/vault-search-mcp
cat > ~/.config/vault-search-mcp/env <<'EOF'
# 데이터 경로
VAULT_PATH=/your/vault/path
GRAPHRAG_DB_PATH=/your/graphrag/index/vault_graph.db
GRAPHRAG_API_URL=http://127.0.0.1:8400
GRAPHRAG_MODE=primary
GRAPHRAG_TIMEOUT_MS=30000

# HTTP 서버 (로컬만 listen, ngrok이 외부 노출)
MCP_HTTP_PORT=8401
MCP_HTTP_HOST=127.0.0.1

# Legacy bearer (CLI/Codex stdio 백업용 — OAuth 모드 시 자동 무시됨)
MCP_AUTH_TOKEN=$(openssl rand -hex 32)

# WorkOS AuthKit (1단계에서 받은 도메인)
WORKOS_AUTHKIT_DOMAIN=your-domain.authkit.app
WORKOS_AUDIENCE=  # AuthKit이 RFC 8707 미지원 — 비워두면 audience 검증 skip

# 외부 노출 URL (RFC 9728 well-known 응답에 포함)
MCP_RESOURCE_URL=https://your-dev-domain.ngrok-free.dev
EOF

chmod 600 ~/.config/vault-search-mcp/env
```

> **`WORKOS_AUTHKIT_DOMAIN`**: `https://` 없이 hostname만 또는 full URL 둘 다 OK (코드가 normalize)
> **`WORKOS_AUDIENCE`**: 비워둠 — AuthKit JWT에 `aud` claim 없음. 검증 시 자동 skip
> **`MCP_RESOURCE_URL`**: ngrok dev domain의 **full URL** (스킴 포함). 끝에 `/` 없이

---

## 5. systemd Services 설정 (5분)

### 5.1 vault-search-http.service (Express 서버)

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/vault-search-http.service <<'EOF'
[Unit]
Description=vault-search-mcp HTTP transport (StreamableHTTP for ChatGPT/Codex)
After=network.target

[Service]
Type=simple
EnvironmentFile=%h/.config/vault-search-mcp/env
ExecStart=/usr/bin/env node /path/to/vault-search-mcp/dist/http.js
Restart=on-failure
RestartSec=5
StandardOutput=append:%h/.cache/vault-search-http.log
StandardError=append:%h/.cache/vault-search-http.log

[Install]
WantedBy=default.target
EOF
```

`/path/to/vault-search-mcp` 부분을 본인 경로로 수정.

### 5.2 ngrok-vault.service (외부 터널)

```bash
cat > ~/.config/systemd/user/ngrok-vault.service <<'EOF'
[Unit]
Description=ngrok tunnel for vault-search-mcp
After=vault-search-http.service
Wants=vault-search-http.service

[Service]
Type=simple
ExecStart=%h/.local/bin/ngrok http --url=YOUR-DEV-DOMAIN.ngrok-free.dev 8401 --log=stdout
Restart=on-failure
RestartSec=10
StandardOutput=append:%h/.cache/ngrok-vault.log
StandardError=append:%h/.cache/ngrok-vault.log

[Install]
WantedBy=default.target
EOF
```

`YOUR-DEV-DOMAIN.ngrok-free.dev`를 본인 dev domain으로 교체. ngrok v3 명령은 `--url=` (또는 `--domain=`) 사용.

### 5.3 활성화 + 시작

```bash
systemctl --user daemon-reload
systemctl --user enable --now vault-search-http.service
systemctl --user enable --now ngrok-vault.service

# 상태 확인
systemctl --user status vault-search-http.service ngrok-vault.service
```

> **이전에 cloudflared 사용 중이었다면**:
> ```bash
> systemctl --user stop cloudflared-vault-search.service
> systemctl --user disable cloudflared-vault-search.service
> ```

---

## 6. 외부 검증 (well-known 4종)

ChatGPT 등록 전 **반드시** 다음 4개 endpoint가 정상 응답하는지 확인:

```bash
DOMAIN=https://YOUR-DEV-DOMAIN.ngrok-free.dev

# 1. healthz
curl -sS $DOMAIN/healthz | python3 -m json.tool
# 기대: {"ok":true,"authMode":"oauth","oauthProvider":"workos",...}

# 2. RFC 9728 (resource metadata)
curl -sS $DOMAIN/.well-known/oauth-protected-resource/mcp | python3 -m json.tool
# 기대: {"resource":"...","authorization_servers":["https://YOUR-AUTHKIT-DOMAIN.authkit.app"],...}

# 3. RFC 8414 (authorization server metadata) — Claude 호환
curl -sS $DOMAIN/.well-known/oauth-authorization-server | python3 -m json.tool
# 기대: issuer/authorization_endpoint/token_endpoint/jwks_uri 모두 채워짐

# 4. RFC 8414 + /mcp suffix — ChatGPT 필수
curl -sS $DOMAIN/.well-known/oauth-authorization-server/mcp | python3 -m json.tool
# 기대: 위 3번과 동일 응답

# 5. 무인증 401 + WWW-Authenticate
curl -sS -i -X POST $DOMAIN/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' | head -15
# 기대: HTTP 401 + WWW-Authenticate: Bearer realm="mcp", resource_metadata="..."
```

5개 모두 통과해야 ChatGPT 등록 가능.

---

## 7. ChatGPT 등록 (Business / Plus / Pro)

### 7.1 Developer Mode 활성화

- **Settings → Connectors** → **Developer Mode** 토글 ON
- Business: **Workspace Settings → Permissions & Roles → Connected Data Developer mode** ON

### 7.2 Custom Connector 만들기

1. **Settings → Connectors** → **+ Create Connector** (또는 **+ 만들기**)
2. **MCP Server** 선택
3. 입력값:
   | 필드 | 값 |
   |---|---|
   | Name | `vault-search` (자유) |
   | Description | `Personal vault search via GraphRAG` |
   | MCP Server URL | `https://YOUR-DEV-DOMAIN.ngrok-free.dev/mcp` |
   | Authentication | **OAuth** (No-auth/Bearer 아님) |
4. **Create**
5. ChatGPT가 자동으로:
   - well-known endpoint fetch
   - WorkOS DCR로 client 자동 등록
   - 사용자에게 WorkOS 로그인 화면 표시
6. 로그인 → 권한 승인 → connector 활성화 완료

### 7.3 Business: Admin Apps 화면

Business workspace는 **Workspace Admin → Apps** 에서 만든 connector가 모든 멤버에게 노출됩니다 (1인 admin이면 본인이 사용 가능). 만든 직후:
- **Enabled (활성화된 앱)** 탭에 표시되어야 함
- **Drafts (초안)** 탭에 남아있으면 검증 실패 → 7.5 트러블슈팅

### 7.4 검증 프롬프트

새 채팅에서 connector 활성화 후:

```
vault-search MCP로:
1. "GraphRAG cron" 으로 search해서 첫 3개 결과 보여줘
2. 첫 번째 결과의 id를 fetch해서 노트 내용 요약해줘
```

기대 결과:
- search → `{results:[{id, title, url}, ...]}`  3개
- fetch → 첫 노트 본문 + 요약

---

## 8. 트러블슈팅 (10대 함정)

### 8.1 silent fail (서버 access log에 흔적 0건)

| 증상 | 원인 | 해결 |
|---|---|---|
| 서버 access log 0건 + ChatGPT "연결 문제" | trycloudflare 도메인 거부 | ngrok으로 교체 (본 가이드) |
| 서버에 도달 + 401 → 그 후 멈춤 | `/.well-known/oauth-authorization-server/mcp` 미구현 | `src/http.ts`에 suffix endpoint 추가 (이미 적용됨) |
| OAuth 성공 후 tools/list 호출 401 | OAuth middleware가 `/.well-known/*` 차단 | wellknown route를 authMiddleware **앞에** 등록 |
| chat에서 "Action 없음" | search/fetch tool 이름 미일치 | `src/index.ts`에 정확히 `search`, `fetch` 이름의 tool 등록 |

### 8.2 OAuth 흐름 silent fail

| 증상 | 원인 | 해결 |
|---|---|---|
| WorkOS 로그인 후 redirect 실패 | redirect URI 미등록 | WorkOS Dashboard → Connect → Applications → Redirects에 `chatgpt.com/connector_platform_oauth_redirect` + `chatgpt.com/connector/oauth/*` 추가 |
| "invalid token" JWT 검증 실패 | issuer URL 형식 (trailing slash) | AuthKit issuer는 trailing slash **없음** (`https://xxx.authkit.app`) |
| audience claim 불일치 | AuthKit JWT에 `aud` 부재 | env에서 `WORKOS_AUDIENCE=` 비워두기 → 코드가 검증 skip |
| DCR 등록 후 token exchange 실패 | `token_endpoint_auth_method` 충돌 | WorkOS DCR이 자동으로 `none` 발급. 수동 client는 `client_secret_basic` 기본값이라 ChatGPT와 충돌 — DCR만 사용 |

### 8.3 CORS / 도메인 신뢰

| 증상 | 원인 | 해결 |
|---|---|---|
| 브라우저 콘솔 CORS 에러 | OPTIONS preflight 401 응답 | `src/http.ts`의 CORS middleware 확인 (OPTIONS → 204) |
| ChatGPT가 marketplace(Smithery)로 fallback UI | URL 검증 실패 | 도메인 변경 (ngrok로) + well-known suffix 추가 |

### 8.4 진단 명령어

```bash
# 서버 access log 실시간 모니터링 (ChatGPT 시도 추적)
journalctl --user -u vault-search-http.service -f

# ngrok 로그
journalctl --user -u ngrok-vault.service -f

# ngrok 로컬 inspector (브라우저)
http://127.0.0.1:4040
```

---

## 9. 보안 노트

- `~/.config/vault-search-mcp/env`는 **chmod 600** (본인만 읽기). git 추적 금지
- `MCP_HTTP_HOST=127.0.0.1` — Express는 localhost만 listen. ngrok이 유일한 외부 진입점
- WorkOS DCR은 등록된 client_id/secret을 자동 관리. 별도 secret 파일 노출 X
- vault 데이터 자체가 민감하면 `WORKOS_AUDIENCE` 강제 + scope 기반 ACL 추가 필요 (현재는 `vault:search`, `vault:context:public`, `vault:context:private`, `vault:graph` scope만 정의되고 enforcement는 로드맵)

---

## 10. 운영 명령

```bash
# 서비스 상태
systemctl --user status vault-search-http.service ngrok-vault.service

# 재시작
systemctl --user restart vault-search-http.service

# 외부 노출 즉시 중단 (vault-search-http는 유지 — 로컬 stdio 클라이언트는 계속 사용 가능)
systemctl --user stop ngrok-vault.service

# 완전 비활성화
systemctl --user disable --now vault-search-http.service ngrok-vault.service

# 로그
tail -f ~/.cache/vault-search-http.log
tail -f ~/.cache/ngrok-vault.log
```

---

## 11. 참고

- 본 가이드의 결정 근거 = 내부 딥리서치 리포트 (32 sources — 번들 미포함)
- ChatGPT MCP OAuth Provider 비교 = 내부 딥리서치 리포트 (30 sources — 번들 미포함)
- 기존 cloudflared + Bearer 시절 가이드 = [`../CHATGPT_CONNECTOR.md`](../CHATGPT_CONNECTOR.md) (deprecated, 보존용)

### 외부 자료

- [OpenAI Apps SDK — Connect from ChatGPT](https://developers.openai.com/apps-sdk/deploy/connect-chatgpt)
- [OpenAI Apps SDK — Authentication](https://developers.openai.com/apps-sdk/build/auth)
- [WorkOS AuthKit MCP Docs](https://workos.com/docs/authkit/mcp)
- [ngrok Linux 설치](https://ngrok.com/docs/getting-started)
- [TypeScript MCP SDK Security Advisory (DNS rebinding)](https://github.com/modelcontextprotocol/typescript-sdk/security/advisories/GHSA-w48q-cv73-mx4w)

---

## 12. 변경 이력

- **2026-04-27** — 초판. cloudflared quick tunnel 거부 패턴 검증 후 ngrok 무료 dev domain으로 전환. WorkOS AuthKit + DCR + well-known suffix 함정 모두 반영. 32-source deep research 결과 반영.
