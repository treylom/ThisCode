---
description: thiscode 메인 wizard — 환경 인식 + Discord 봇 셋업 + 첫 대화 검증
allowed-tools: Bash Read Write Edit AskUserQuestion Skill
disable-model-invocation: true
---

# /thiscode:start — 메인 wizard

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

> 새 머신에 Claude Code + Discord 봇 통합 환경을 처음 셋업할 때 진입점.

$ARGUMENTS

---

## Step 0-A. 설치 방식 선택 — **가장 먼저, 다른 어떤 것보다 앞에** (R1)

이 질문이 **사용자와의 첫 상호작용**이다. 환경 점검·도구 확인보다도 앞이다.

`AskUserQuestion` 으로 묻는다:

> **설치를 어떻게 진행할까요?**
> - **자동** (권장) — 제가 최대한 직접 진행합니다. 계정 로그인·캡차처럼 **제가 대신하면 안 되는 곳**에서만 멈춰서 부탁드립니다.
> - **수동** — 단계마다 무엇을 해야 하는지 안내받고 직접 진행하겠습니다.

고른 값을 **상태 파일에 기록한다** (이후 모든 관문 판단이 이 값을 읽는다):

```bash
mkdir -p ~/.thiscode
printf 'install:\n  mode: %s\n' "auto"    # 또는 manual — 사용자가 고른 값
  > ~/.thiscode/install-state.yaml
```

### 🔴 「자동」을 고른 뒤의 계약 (R2 — 이게 이 wizard 의 핵심이다)

**「직접 해주셔야 할 것」을 사용자에게 띄우려는 «모든» 지점에서, 띄우기 전에 이 명령을 실제로 부른다:**

```bash
bash <플러그인루트>/scripts/install-gate.sh <관문이름>
```

| 결과 | 무엇을 해야 하나 |
|---|---|
| **exit 0** | 안내를 띄워도 된다 (계약 명단에 등재된 관문 = 대신 하면 안 되는 것, 또는 사용자가 manual 을 골랐다) |
| **exit 1 또는 2** | 🔴 **먼저 자동으로 «한 번 실제로 시도»한다.** 성공하면 안내를 **띄우지 않는다.** 실패했을 때만 안내하고, **실패 사유를 함께** 보여준다 |

**「시도」는 «판단»이 아니라 «실행»이다.** 「이건 사람이 해야 할 것 같다」는 시도가 아니다 — 도구를 실제로 호출해 보고 그 결과를 봐야 한다. 판단만 하면 그건 이 계약이 생기기 전과 똑같은 동작이다.

계약 명단·사유는 `configs/install.yaml` 에 있다. **명단에 없는 관문의 기본값은 «시도»다** — 그래야 새로 생긴 관문이 조용히 수동으로 새지 않는다.

### R5 — 브라우저 도구는 끝까지 쓴다

`configs/install.yaml` 의 `browser_tools_required: true` 이면:
- 브라우저 도구(playwright / claude-in-chrome)가 없다고 **수동으로 떨어지지 않는다.** 먼저 **설치를 시도**한다 (Slack CLI 자동 설치가 이미 같은 전례다).
- 도구를 **시작만 하고 사용자에게 넘기지 않는다.** 중간에 그만두게 되면 **그 사유를 남긴다.** 사유 없는 이탈은 계약 위반이다.
- 단, 계약 명단에 등재된 관문(캡차·자격증명 등) 앞에서 멈추는 것은 **완주 실패가 아니라 설계된 정지**다. 이 둘을 섞어 보고하지 않는다.

---

## 4-step 부트스트랩 (순정 Claude Code 가정)

```
Step 0. install-hooks      → SessionStart + UserPromptSubmit hook merge (~/.claude/settings.json)
Step 1-5. 본 wizard         → 환경 + Discord 봇 + 페어링 (아래 흐름)
```

순정 Claude Code 에 hook 이 없으면 soul.md 가 단순 markdown 파일로 방치 → 페르소나 inject 안 됨 (5/12 회귀 R5). hooks 먼저 등록.

```bash
/thiscode:install-hooks   # 본 wizard 진입 전 실행 권장 (한 번만)
```

이미 vault 운영 중인 사용자 (기존 hook 존재) 는 본 step skip.

---

## 진행 흐름 (agent 가 사용자에게 안내)

### Step 1. 환경 점검 (자동, 사용자 input 0회)

```bash
uname -s                                  # → "Linux" or "Darwin"
grep -i microsoft /proc/version 2>/dev/null && echo "WSL"
command -v tmux git curl node claude     # 의존 도구 확인
```

부족한 도구 있으면 `bash install.sh` 실행 안내 (또는 `curl -fsSL https://raw.githubusercontent.com/treylom/ThisCode/main/install.sh | bash`).

### Step 2. Discord 봇 생성 (기본 = 자동 완주, B7)

본 step 은 `/thiscode:create-bot` Step 3 이 담당합니다(자동화 권장, Steps 3-4 와 동일 위임 패턴) — 브라우저 자동화 도구가 이 세션에 있으면 **묻지 않고 기본으로** 앱 생성부터 승인까지 완주하고, hCaptcha·비밀번호/다단계 인증(MFA) 모달 2곳에서만 "여기만 눌러(입력해) 주세요" 하고 멈춥니다.

```bash
# 자동화 — 권장 (Step 3-4 와 통합 실행됨)
/thiscode:create-bot
```

#### (manual) Step 2. Discord 봇 생성 안내 (도구 없을 때, 사용자 수동)

브라우저로 https://discord.com/developers/applications 접속:

1. "New Application" → 이름 (예: `<your-bot-name>`) → **캡차 1회(사람)**
2. 좌측 "Bot" 탭 → "Reset Token" → **비밀번호 입력(사람)** → 토큰 복사
3. **같은 "Bot" 탭 하단 "Privileged Gateway Intents"** 에서 **"Message Content Intent" 와 "Server Members Intent" 둘 다 ON** → Save
   - ⚠️ Message Content 미설정 시 토큰·초대가 정상이어도 봇이 서버 채널 메시지 내용을 못 읽어 무반응 (DM 은 예외). "토큰 valid 인데 채널 답 없음" 1순위 원인.
   - ⚠️ Server Members 미설정 시 봇 템플릿이 `intents.members` 를 요청하므로 **기동 즉시 `PrivilegedIntentsRequired` 크래시** — 이 단계는 생략 불가.
4. OAuth2 → URL Generator
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: Send Messages, Read Messages, Read Message History, Add Reactions, Attach Files, Embed Links
5. 생성된 URL 로 봇을 본인 Discord 서버 또는 DM 가능 채널에 초대 → **승인(사람)**

전체 권한 목록(스레드 4종 포함)·비공개 채널 멤버 추가·데스크톱 앱 가로채기 대응 등 상세는 `skills/create-bot/SKILL.md` Step 3 이 정본이다 — 사본 drift 방지를 위해 본 파일엔 요약만 둔다.

> ⚠️ **다봇 셋업 시 — 봇마다 별도 초대 필수**: 봇은 각자 독립 Discord 애플리케이션이라
> OAuth 초대도 **봇 앱마다 따로** 해야 합니다. 신규 봇 초대를 빠뜨리면 그 봇만 무반응
> (Discord 는 같은 서버 공유 봇하고만 DM 가능). 무반응 진단 순서 →
> [docs/08-debug-노하우.md J-3](../docs/08-debug-노하우.md).

### Step 3-4. 봇 디렉토리 + soul.md 자동 셋업 (자동화 권장)

본 두 step 은 `/thiscode:create-bot` 슬래시가 일괄 처리합니다 (대화형). 수동으로 하고 싶을 때만 아래 manual 흐름 참고.

```bash
# 자동화 — 권장
/thiscode:create-bot
```

`create-bot` 가 묻는 항목:
- 봇 이름 (예: `karpathy`, `mybot`)
- Discord 토큰 (Step 2 에서 발급)
- 페르소나 template 선택 (research-bot / writing-bot / schedule-bot / general-assistant / custom)

자동 수행:
- `~/.claude/channels/discord-<bot-name>/` 디렉토리 신설 (chmod 700)
- `.env` 작성 (chmod 600) — `DISCORD_BOT_TOKEN`
- `soul.md` 작성 — 선택 template 안 placeholder 자동 치환

#### (manual) Step 3. 봇 토큰 입력

```bash
mkdir -p ~/.claude/channels/discord-<bot-name>
chmod 700 ~/.claude/channels/discord-<bot-name>
cat > ~/.claude/channels/discord-<bot-name>/.env <<EOF
DISCORD_BOT_TOKEN=<입력 토큰>
EOF
chmod 600 ~/.claude/channels/discord-<bot-name>/.env
```

⚠️ 토큰을 Discord 본문이나 git 에 노출 금지.

#### (manual) Step 4. soul.md 페르소나 결정

template 5종 중 선택 또는 자유 작성:

| template | 어울리는 사용 | 파일 |
|---|---|---|
| `general-assistant` | 범용 비서 (default) | `templates/soul-general-assistant.md` |
| `research-bot` | 자료조사·교차검증 | `templates/soul-research-bot.md` |
| `writing-bot` | 글쓰기·퇴고 | `templates/soul-writing-bot.md` |
| `schedule-bot` | 일정·Todo | `templates/soul-schedule-bot.md` |
| `custom` | 자유 페르소나 (anatomy 가이드 포함) | `templates/soul-custom.md` |

선택 후 다음 위치 생성:
```
~/.claude/channels/discord-<bot-name>/soul.md
```

content 는 YAML frontmatter (`name + description + version + created + triggers`) + 강제 페르소나 규율 + 시그니처 + 팀 + Why 패턴.

### Step 5. 페어링 + 첫 대화 검증

```bash
tmux new-session -s <bot-name>
cd ~/<project> && claude
```

Discord 앱에서 봇에 DM:
```
안녕
```

봇 응답 확인 ✅ → 첫 대화 검증 완료.

---

## 검증 체크리스트

- [ ] `claude --version` ≥ 2.x
- [ ] tmux session 정상 진입
- [ ] Discord 봇 DM 수신 → 봇 응답 표시
- [ ] soul.md 페르소나 어휘가 응답에 자연 포함

---

## 다음 step

추가 봇 / 회의실 / 자가 업데이트 / Codex 검증:

- `/thiscode:add-bot` — 추가 봇 1개 신설
- `/thiscode:open-meeting` — 회의실 폴더 신설 (다 봇 협업 4-file)
- `/thiscode:codex-check` — Codex CLI 검증 (호출 layer 활성)
- `/thiscode:self-update` — 메인봇 시작 시 git pull 체크
- `/thiscode:install-hooks` — hook 재정비 (settings.json drift 시)
- `/thiscode:create-bot` — 추가 봇 자동 셋업 반복
