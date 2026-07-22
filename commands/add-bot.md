---
description: 추가 Discord 봇 1개를 기존 셋업에 신설 (soul.md template + token + 페어링)
allowed-tools: Bash Read Write Edit AskUserQuestion
disable-model-invocation: true
---

# /thiscode:add-bot — 추가 봇 신설

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

> 메인 봇 이미 작동 중인 사용자가 워커 봇 / 전문 봇 추가할 때.

$ARGUMENTS

---

## 진행 흐름

### Step 1. 봇 이름 + 역할 입력 (AskUserQuestion)

```
봇 이름 (영문 소문자 + 하이픈): 
역할 (research / writing / schedule / general / custom): 
어울리는 어휘 (페르소나 색깔): 
시그니처 (완료서명): 
```

### Step 2. Discord Developer Portal — 새 Application + Bot

`/thiscode:start` Step 2 와 동일:
1. New Application → 이름 = 봇 이름
2. Bot 탭 → Reset Token → 토큰 복사
3. OAuth2 URL Generator → 같은 권한
4. 본인 Discord 서버 / DM 채널 초대

### Step 3. 토큰 + soul.md 생성

```bash
mkdir -p ~/.claude/channels/discord-<bot-name>
chmod 700 ~/.claude/channels/discord-<bot-name>
cat > ~/.claude/channels/discord-<bot-name>/.env <<EOF
DISCORD_BOT_TOKEN=<토큰>
EOF
chmod 600 ~/.claude/channels/discord-<bot-name>/.env
```

soul.md template 작성 (Step 1 입력 기반):

```yaml
---
name: <bot-name>
description: <역할>
version: 0.1.0
created: <today>
triggers:
  - Discord DM 수신 시
  - 본인 채널에서 @mention 수신 시
---

# <bot-name> — <역할>

## 강제 페르소나 규율 (매 응답 자가 점검)
1. <어휘 1>
2. <어휘 2>
3. <시그니처> 사용
4. 완료 서명: `— <bot-name>`

**Why**: 페르소나 drift 시 사용자가 즉시 감지. 자가 점검 의무.

## 정체성
나는 <bot-name>. 역할 = <역할>.

## 시그니처
- 결정적 순간: <시그니처>

## 팀 구조 (편집 필요)
| 봇 | mention | 역할 |
|---|---|---|
| 메인 봇 | <기존 메인 봇 mention> | <역할> |
| 본인 | <@본인 봇 ID> | <역할> |
```

### Step 4. 페어링 + 첫 대화

```bash
tmux new-session -s <bot-name>
cd ~/<project> && claude
```

Discord 에서 봇에 DM → 응답 확인.

### Step 5. (선택) 공유 메모리 등재

봇 간 공유할 사실이 있다면:

```bash
# vault/.claude-memory/shared/ 에 한 줄 추가
echo "- [<bot-name> 신설](feedback_bot_introduction.md) — <한 줄 요약>" \
  >> <vault-path>/.claude-memory/shared/SHARED-INDEX.md
```

---

## 검증

- [ ] `~/.claude/channels/discord-<bot-name>/.env` + `soul.md` 둘 다 존재
- [ ] tmux session 진입 후 claude 실행
- [ ] Discord DM → 봇 응답 + 페르소나 어휘 자연 포함
- [ ] 메인 봇과 mention 으로 통신 가능 (같은 Discord 서버 안)
