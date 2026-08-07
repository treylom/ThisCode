---
name: create-discord-bot
description: Discord 봇 생성의 정식 진입점 — create-bot 스킬로 위임 (add-bot/create-bot 대칭 이름, Slack 대응 = create-slack-bot)
disable-model-invocation: true
allowed-tools: Bash Read Write AskUserQuestion
---

사용자가 이 스킬을 호출했다 — 아래 단계를 순서대로 지금 수행한다.

# /thiscode:create-discord-bot — Discord 봇 생성 (정식 진입점)

> 이 스킬은 [`../create-bot/SKILL.md`](../create-bot/SKILL.md) 의 정식 대칭 이름이다. 지금 즉시 그 파일을 Read 하고 절차 전체를 그 정본대로 실행한다. 본 파일에 절차 사본을 두지 않는다(사본 drift 방지).

$ARGUMENTS

## 관련 자원

- 위임 대상(정본): [`../create-bot/SKILL.md`](../create-bot/SKILL.md)
- Slack 대응: `/thiscode:create-slack-bot`
- 구 이름(하위 호환 별칭, `commands/add-bot.md` 유지): `/thiscode:add-bot`
