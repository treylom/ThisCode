---
name: meetings
description: Use when launching multi-bot collaboration meetings with permanent records. Defines the 4-file standard (00-context/01-spec/02-progress/03-outcome), source-backed cross-check before folder creation, Discord REST API thread creation (POST /channels/{id}/threads, type=11, python urllib pattern), mandatory audience direct mention, and 3-channel parallel reporting (meeting outcome + Avengers main + initiator bot mention).
license: MIT
compatibility: Discord 봇 운영 환경 + 회의 polled audience ≥2 봇
metadata:
  author: treylom
  version: "0.1.0"
  hermes:
    tags: [Meetings, Discord, BotOrchestration]
---

# meetings

> **사용 시점**: 봇 2개 이상이 협업하는 회의·brainstorming 진행 시. agenda + 10분 이상 cap + 영구 기록 필요.

## 4-file 표준 (vault `.claude-meetings/` SoT)

```
<vault-or-repo>/.claude-meetings/<YYYY-MM-DD>-<topic>/
├── 00-context.md       # trigger / audience / scope / Discord 스레드 ID
├── 01-spec.md          # Q&A 진행 / decision lock / 미결
├── 02-progress.md      # timeline (KST)
└── 03-outcome.md       # 회의 마감 후 결론 + 후속 action
```

audience 봇 수 N 분기:
- N=0 (사용자만) → 회의 폴더 X, T1 shared/ 직접 등재
- N=1 (사용자 + 봇 1) → outcome-only.md 한 파일
- N≥2 → Full 4-file (본 skill 적용)

## 회의 신설 전 — 출처 기반 cross-check (필수)

⚠️ "회의 폴더 신설" 단정 전 다축 grep 으로 같은 topic 이미 진행 중인지 확인.

```bash
# 다축 1: 정확한 위치
find <vault-or-repo>/.claude-meetings -maxdepth 2 -type d -iname "*<topic-keyword>*"

# 다축 2: README/INDEX
grep -r "<topic>" <vault>/.claude-meetings/INDEX.md 2>/dev/null

# 다축 3: 다른 봇이 시작했을 가능성
find ~ -name "*.claude-meetings*" -type d 2>/dev/null
```

→ 단일 grep 으로 hit 0 단정 ❌ (single-grep trap 회귀). 다축 (정확 path + INDEX + 다른 봇 영역) cross-validate 의무.

## Discord 스레드 신설 — REST API 직접 패턴

mcp Discord reply 도구가 thread 생성을 지원 안 할 때 (또는 도구 죽었을 때) — 봇 토큰으로 REST API 직접 호출.

### Python urllib 패턴

```bash
set -a
source ~/.claude/channels/discord-<bot-name>/.env
set +a

python3 << 'PYEOF'
import os, urllib.request, json

token = os.environ['DISCORD_BOT_TOKEN']
H = {
    'Authorization': f'Bot {token}',
    'Content-Type': 'application/json',
    'User-Agent': 'DiscordBot (thiscode 0.1.0)'
}

def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST', headers=H)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'_err': e.code, '_msg': e.read().decode()[:300]}

PARENT = '<parent-channel-id>'   # 어벤져스 또는 일반 채널

thread = post(f"https://discord.com/api/v10/channels/{PARENT}/threads", {
    "name": "<topic> — meeting",
    "type": 11,                    # PUBLIC_THREAD
    "auto_archive_duration": 1440  # 24h
})
print('THREAD:', thread.get('id') or thread.get('_err'), thread.get('name', thread.get('_msg', '?'))[:200])
PYEOF
```

→ thread_id 받은 후 `00-context.md` 의 `discord_thread:` 필드 채워넣기.

## audience direct mention 의무

⚠️ 회의 신설 후 audience 봇 들에게 **Discord direct mention 필수**. 텍스트 명시만으로 ❌.

```python
# 회의 스레드 안에서:
content = f"<@{bot1_id}> [회의 신설] <topic>\n- 위치: <meeting-path>\n- 00-context.md 참조\n- audience: <봇 list>"
```

이유: 텍스트 명시는 봇이 못 봄 (push notification 안 감). mention 으로 호출해야 봇이 인지 + reply 가능.

## 3-channel 병행 보고 (회의 마감 시)

⚠️ 회의 outcome 발생 시 다음 3 채널 동시 보고:

1. **회의 스레드 안** — `03-outcome.md` 작성 + 스레드에 마감 메시지
2. **어벤져스 본문 (또는 메인 채널)** — 단독 작업 완료 보고 (대화 기록방 지속)
   - 형식: `✅ [<topic>] 완료. 산출: <경로>. 03-outcome 참조. — <bot>`
3. **발의 봇 direct mention** — orchestrator 또는 발의 봇에게 mention 알림

회의실 vault 가 본문을 대체 ❌. 본문 발화도 유지 (Discord 대화 기록은 별도 영역).

## 진행 흐름 — agent 가 사용자에게 안내

### Step 1. 회의 메타 입력 (AskUserQuestion)

```
주제 (kebab-case):
audience 봇 mention list:
trigger (왜 신설?):
예상 시간:
```

### Step 2. 출처 기반 cross-check (자동, 위 다축 grep)

같은 topic 진행 중이면 → 기존 폴더 reuse 또는 user confirm 후 새 폴더.

### Step 3. 폴더 신설 + 4 파일 skeleton

`mkdir -p` + 4 파일 frontmatter+빈 헤더.

### Step 4. Discord 스레드 신설 (위 python 패턴)

parent 채널 결정 (어벤져스 / 일반 / 봇별 본부 채널) → REST API POST.

### Step 5. audience 봇 mention (위 패턴)

각 audience 봇에게 direct mention 메시지 발송.

### Step 6. 회의 진행

agent 가 회의 진행 중 `02-progress.md` 에 timeline (KST) 기록. decision lock 시 `01-spec.md` 에 등재.

### Step 7. 마감 (3-channel 병행)

위 3-channel 패턴 따라 outcome 보고.

## 트러블슈팅

| 증상 | 원인 | 대응 |
|---|---|---|
| Discord reply 도구 'text.length undefined' 에러 6번 연속 | mcp 도구 죽음 | python urllib REST API 우회 (본 skill §Discord 스레드 신설) |
| audience 봇 답 안 옴 | mention 안 함 (텍스트만) | direct mention 으로 재 발화 |
| 회의 outcome 만 vault 에 두고 본문 발화 X | 3-channel 보고 누락 | 본문 + 발의 봇 mention 추가 발화 |
| 같은 topic 회의 2개 신설 | 출처 기반 cross-check skip | 한 쪽 archive + 다른 쪽으로 통합 |

## 관련 자원

- 회의 스레드·채널 거버넌스 규약: [../../docs/05-meeting-thread-protocol.md](../../docs/05-meeting-thread-protocol.md)
- 공유 메모리 skill: [../shared-memory/SKILL.md](../shared-memory/SKILL.md)
- slash command: [../../commands/open-meeting.md](../../commands/open-meeting.md)
