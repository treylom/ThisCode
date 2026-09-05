---
description: 회의실 폴더 신설 (다 봇 협업 4-file 표준 — 00-context / 01-spec / 02-progress / 03-outcome)
allowed-tools: Bash Read Write AskUserQuestion
disable-model-invocation: true
---

# /thiscode:open-meeting — 회의실 신설

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

> 다 봇 협업 또는 깊은 brainstorming 진행 시 영구 기록용 폴더 신설.

$ARGUMENTS

---

## 회의실 spec (vault 표준)

위치: `<vault-or-project>/.claude-meetings/<YYYY-MM-DD>-<topic>/`

4-file 표준:
- `00-context.md` — trigger, audience, scope
- `01-spec.md` — Q&A 진행, decision lock, 미결
- `02-progress.md` — timeline (KST)
- `03-outcome.md` — 회의 마감 후 결론 + 후속 action

Stop hook active marker:
- `ACTIVE.md` — 현재 회의가 열려 있음을 표시하는 marker. `hooks/meeting-stop-reread.sh` 가 기본으로 읽는 기준 파일.
- 다른 파일명을 쓰는 설치자는 `MEETING_ACTIVE_FILE=<absolute-path>` 로 override.

봇 N 분기:
- 0 봇 (사용자만) → 공유 memory 직접 등재, 폴더 X
- 1 봇 → outcome-only.md
- ≥2 봇 → Full 4-file (본 slash 가 신설)

---

## 진행 흐름

### Step 1. 회의 정보 입력 (AskUserQuestion)

```
주제 (kebab-case, 영문 또는 한글): 
audience 봇 mention list (예: <@123>, <@456>): 
trigger (왜 회의 신설?): 
예상 시간: 
```

### Step 2. 폴더 신설

```bash
TODAY=$(date +%Y-%m-%d)
TOPIC=<input-topic>
MEETING_DIR=<vault-or-project>/.claude-meetings/${TODAY}-${TOPIC}
mkdir -p ${MEETING_DIR}
```

### Step 3. 4 파일 skeleton + ACTIVE marker 생성

`00-context.md`:
```yaml
---
title: <topic> — context
date: <today>
status: in-progress
audience:
  - <봇 1>
  - <봇 2>
discord_thread: <thread-id-or-pending>
trigger: <입력>
---

# 회의 context

## Trigger
<입력>

## audience 결정
- <봇 1> — <역할>
- <봇 2> — <역할>

## scope
<범위 정의>
```

`01-spec.md` / `02-progress.md` / `03-outcome.md` 도 skeleton 생성 (frontmatter + 빈 헤더).

`ACTIVE.md`:
```markdown
# active meeting

thread_id: <thread-id-or-pending>
meeting_dir: ${MEETING_DIR}
progress_file: ${MEETING_DIR}/02-progress.md

Before stopping during this meeting, re-read `02-progress.md`, append a KST
progress row for meaningful start/done/blocked transitions, then report through
the meeting thread.
```

`ACTIVE.md` 는 회의 마감 시 삭제하거나 `03-outcome.md` 작성 뒤 `status: closed` 로 바꾼다.
Stop hook 이 다른 marker 를 읽게 하려면 `MEETING_ACTIVE_FILE=/absolute/path/to/ACTIVE.md`
환경변수를 사용한다.

### Step 4. Discord 스레드 신설 안내 (선택)

```bash
# 메인 (또는 적합) 채널 안에 새 스레드 생성
# Discord REST API 또는 봇 도구로:
POST /channels/<parent-channel-id>/threads
{
  "name": "<topic> — meeting",
  "type": 11,  # PUBLIC_THREAD
  "auto_archive_duration": 1440
}
```

스레드 ID 받으면 `00-context.md` 의 `discord_thread:` 필드 채워넣기.

### Step 5. audience 봇 mention (필수)

회의 신설 후 audience 봇 들에게 Discord direct mention. 텍스트 명시만으로는 부족:

```
<@봇1> [회의 신설] <topic>
- 위치: <vault>/.claude-meetings/<topic>/
- 00-context.md 참조
- audience: <봇 list>
```

---

## 검증

- [ ] 4 파일 모두 존재 (`00-context.md` 외 3개)
- [ ] Stop hook marker 존재 (`ACTIVE.md` 또는 `MEETING_ACTIVE_FILE` override)
- [ ] audience 봇 list 정확 mention
- [ ] Discord 스레드 신설 시 thread_id 가 00-context 에 기록
- [ ] 회의 마감 시 `03-outcome.md` 가 후속 action + 시간 기반 caller (스케쥴 봇) 에 캘린더 등재
