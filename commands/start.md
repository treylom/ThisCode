---
description: thiscode 메인 wizard — 환경 인식 + Discord 봇 셋업 + 첫 대화 검증
allowed-tools: Bash Read Write Edit AskUserQuestion Skill
disable-model-invocation: true
---

# /thiscode:start — 메인 wizard

> 새 머신에 Claude Code + Discord 봇 통합 환경을 처음 셋업할 때 진입점.

$ARGUMENTS

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

### Step 2. Discord 봇 생성 안내 (사용자 수동)

브라우저로 https://discord.com/developers/applications 접속:

1. "New Application" → 이름 (예: `Karpathy-mybot`)
2. 좌측 "Bot" 탭 → "Reset Token" → 토큰 복사
3. OAuth2 → URL Generator
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: Send Messages, Read Messages, Read Message History, Add Reactions, Attach Files, Embed Links
4. 생성된 URL 로 봇을 본인 Discord 서버 또는 DM 가능 채널에 초대

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
