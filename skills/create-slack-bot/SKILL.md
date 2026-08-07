---
name: create-slack-bot
description: Slack 봇 연결의 정식 진입점 — slack-configure 스킬로 위임 (create-bot의 Slack 대응, 대칭 이름)
disable-model-invocation: true
allowed-tools: Bash Read Write AskUserQuestion
---

사용자가 이 스킬을 호출했다 — 아래 단계를 순서대로 지금 수행한다.

# /thiscode:create-slack-bot — Slack 봇 연결 자동 셋업 (정식 진입점)

> 이 스킬은 [`../slack-configure/SKILL.md`](../slack-configure/SKILL.md) 의 정식 대칭 이름이다. 지금 즉시 그 파일을 Read 하고 절차 전체를 그 정본대로 실행한다. 본 파일에 절차 사본을 두지 않는다(사본 drift 방지).

$ARGUMENTS

## 관련 자원

- 위임 대상(정본): [`../slack-configure/SKILL.md`](../slack-configure/SKILL.md)
- Discord 대응: `/thiscode:create-discord-bot`
- 구 이름(하위 호환 별칭, `commands/slack-configure.md` 유지): `/thiscode:slack-configure`
