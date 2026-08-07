---
description: 신규(또는 추가) Claude Code 세션을 Slack에 연결 — claude-channel-server 브리지 자동 셋업 (create-bot의 Slack 대응)
allowed-tools: Bash Read Write AskUserQuestion
disable-model-invocation: true
---

# /thiscode:slack-configure — Slack 봇 연결 자동 셋업

> **별칭 안내**: 정식 이름은 `/thiscode:create-slack-bot` — 본 커맨드는 하위 호환 별칭으로 유지된다(기존 문서·메모리 참조 보존).

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

> Discord 대신 (또는 추가로) Slack으로 Claude Code 세션을 페어링하고 싶은 사용자용. `/thiscode:create-bot`(Discord 판)의 Slack 대응.

$ARGUMENTS

---

## 무엇을 하는가

`claude-channel-server` 브리지(공식 `claude/channel` MCP 프로토콜)를 Slack 워크스페이스에 얹어, 이 Claude Code 세션이 Slack DM·채널 메시지를 받고 `reply` 도구로 답할 수 있는 상태까지 자동으로 만든다. 사람이 실제로 클릭·입력해야 하는 지점(Slack CLI 로그인, 워크스페이스 설치 승인, 토큰 복사·붙여넣기, 첫 채널 로드 확인 — 총 4곳 + 조건부 1곳)에서만 멈춰 안내하고 기다린다. 그 외는 전부 자동 실행.

## 진행 흐름 (요약 — 전문은 스킬 본문)

이 커맨드는 `slack-configure` 스킬을 그대로 호출한다 — **`Skill` 도구로 `slack-configure`를 invoke**해 아래 단계를 순서대로 수행한다. 상세 절차(브리지 자동 빌드 → 봇 이름/페르소나 확인 → Slack CLI 로그인 → 앱 매니페스트 생성·동기화 → 워크스페이스 설치 승인 → 상태 디렉토리 확보(기존 봇 보호) → 채널 확보 → 토큰 입력 → `.env` 검증 → `.mcp.json` 등록 → resident server 기동 → 첫 확인 다이얼로그 → 검증)의 정본은 [`../skills/slack-configure/SKILL.md`](../skills/slack-configure/SKILL.md)다 — 여기서 다시 옮겨 적지 않는다(정본 이원화·drift 방지).

기술 참고서(프로토콜·아키텍처·보안 모델·트러블슈팅 전체 목록)는 [`../skills/slack-bridge/SKILL.md`](../skills/slack-bridge/SKILL.md).

## 사람 관문 (총 4곳 + 조건부 1)

1. Slack CLI 로그인 (`slack login`)
2. 워크스페이스 설치 승인 (브라우저 "허용" 클릭)
3. (조건부) App Home 메시지 탭 토글 — 매니페스트 동기화가 반영 못 했을 때만
4. Bot Token / App Token 복사·붙여넣기
5. Claude Code 첫 기동 시 `--dangerously-load-development-channels` 확인 다이얼로그

## 검증 (요약 — 전체 체크리스트는 스킬 본문)

- [ ] `$STATE_DIR/.env` 존재 + chmod 600 + 필수 키 4개(`SLACK_BOT_TOKEN`·`SLACK_APP_TOKEN`·`ALLOWED_SLACK_USER_ID`·`SLACK_CHANNEL_ID`)
- [ ] resident server 로그에 `bridge live — channel ..., allowed user ...`
- [ ] `.mcp.json`에 `mcpServers.slack-channel` 등록
- [ ] Slack DM → 세션에 메시지 도착 → `reply` 응답 → Slack에 표시 ✅

## 관련 자원

- 기술 참고서: [`../skills/slack-bridge/SKILL.md`](../skills/slack-bridge/SKILL.md)
- Discord 판(공유 로직 정본): [`../skills/create-bot/SKILL.md`](../skills/create-bot/SKILL.md)
