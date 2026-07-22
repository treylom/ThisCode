---
description: Codex CLI 설치 + OAuth 인증 + 모델 picker 검증 (thiscode 의 Codex 호출 layer 가 동작하는지 확인)
allowed-tools: Bash Read AskUserQuestion
disable-model-invocation: true
---

# /thiscode:codex-check — Codex CLI 검증

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

> thiscode 의 codex 호출 layer (`/tofu-at-codex`, `codex-exec-bridge` skill, subprocess `codex exec` 패턴) 가 동작하려면 Codex CLI 가 install + login + 모델 picker 정상이어야 함. 본 슬래시가 5 step 으로 검증.

$ARGUMENTS

---

## 진행 흐름

### Step 1. Codex CLI 설치 확인

```bash
command -v codex && codex --version
```

- ✅ `codex 0.x.x` 출력 → Step 2
- ❌ command not found → 설치 안내:
  ```bash
  npm install -g @openai/codex
  ```
  설치 후 새 터미널 열고 재실행.

### Step 2. OAuth 인증 (codex login)

```bash
[ -f ~/.codex/auth.json ] && echo "auth.json 존재" || echo "미인증 — codex login 필요"
```

- ✅ `~/.codex/auth.json` 존재 → Step 3
- ❌ 미인증 →
  ```bash
  codex login
  ```
  브라우저 OAuth 진행 (ChatGPT 계정 로그인 — Plus 이상 권장 — 자세한 등급별 quotas 는 docs/06-claude-code-server.md 참조)

### Step 3. 모델 picker 확인

```bash
codex model 2>&1 | head -20
```

- ✅ `gpt-5.5` 표시 → Step 4
- ❌ `gpt-5.5` 안 보임 → `codex update` 또는 `npm update -g @openai/codex` 후 재실행

### Step 4. Ephemeral 테스트 호출

```bash
codex exec --no-stream "ping" 2>&1 | head -10
```

- ✅ 응답 받음 → Step 5
- ❌ rate limit → 잠시 대기 후 재시도
- ❌ auth error → `codex login` 다시
- ❌ network error → 인터넷 연결 확인

### Step 5. /tofu-at-codex 슬래시 호환성 (선택)

thiscode 의 `/tofu-at-codex` 또는 `codex-exec-bridge` skill 이 install 되어 있다면:

```bash
# .claude/scripts/setup-tofu-at-codex.sh 존재 시
[ -f .claude/scripts/setup-tofu-at-codex.sh ] && bash .claude/scripts/setup-tofu-at-codex.sh
```

10/10 통과 확인 시 codex 호출 layer 가 plugin 안에서 정상 동작.

---

## 결과 보고 (agent → 사용자)

```
✅ Codex CLI: 0.x.x (검증 완료)
✅ OAuth: ~/.codex/auth.json 존재
✅ 모델: gpt-5.5 picker 정상
✅ Ephemeral test: 응답 OK (Nms)
✅ /tofu-at-codex 호환: 10/10 (or skip)

→ codex 호출 layer 활성. 이제 /tofu-at-codex / codex-exec-bridge / subprocess pattern 사용 가능.
```

---

## 트러블슈팅

| 증상 | 원인 | 대응 |
|---|---|---|
| `codex: command not found` | npm 글로벌 install 안 됨 | `npm install -g @openai/codex` + 새 터미널 |
| `codex login` 브라우저 안 열림 | headless 환경 | device code flow 사용 (`codex login --device`) |
| `gpt-5.5` 모델 picker 미표시 | codex CLI 옛 버전 | `npm update -g @openai/codex` |
| `rate limit exceeded` | ChatGPT Plus 주간 quota 도달 | 다음 주 reset 또는 OpenRouter API key fallback |
| codex exec timeout | 네트워크 또는 reasoning 길이 | `--timeout 300` 명시 |

---

## 관련 자원

- vault `.claude/commands/tofu-at-codex.md` — Codex 하이브리드 팀 v2.2 spec
- vault `.claude/skills/codex-exec-bridge/` — 6-file skill (CLI 호출 + 상태 파일 + Dynamic Gate + 에러 복구 + 팀 통신)
- `codex CC plugin` (2026-05-11) — `/plugin marketplace add openai/codex-plugin-cc` 후 `/codex:rescue`, `/codex:adversarial-review` 등 슬래시 활용
