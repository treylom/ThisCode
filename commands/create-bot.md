---
description: 새 Discord 봇 디렉토리 (~/.claude/channels/discord-<bot-name>/) 생성 + .env + soul.md template 자동 셋업
allowed-tools: Bash Read Write AskUserQuestion
disable-model-invocation: true
---

# /thiscode:create-bot — 봇 디렉토리 생성

> 새 봇 1개의 `~/.claude/channels/discord-<bot-name>/` 디렉토리 + `.env` (토큰) + `soul.md` (페르소나) 자동 셋업.

$ARGUMENTS

---

## 진행 흐름

### Step 1. 봇 이름 입력 (AskUserQuestion)

```
봇 이름 (영문 소문자 + 하이픈, 예: karpathy / research / writing): 
```

검증: `^[a-z][a-z0-9-]*$` 패턴, 1-32자. (Discord 봇 이름 규칙 + 디렉토리 안전)

### Step 2. 봇 디렉토리 생성

```bash
BOT_DIR="$HOME/.claude/channels/discord-${BOT_NAME}"

if [ -d "$BOT_DIR" ]; then
  echo "❌ $BOT_DIR 이미 존재 — 다른 이름 또는 삭제 후 재시도"
  exit 1
fi

mkdir -p "$BOT_DIR"
chmod 700 "$BOT_DIR"
```

### Step 3. Discord 봇 생성 안내 (Developer Portal)

브라우저로 https://discord.com/developers/applications:
1. "New Application" → 이름 = `<봇 이름 또는 별칭>`
2. 좌측 "Bot" 탭 → "Reset Token" → 토큰 복사
3. **같은 "Bot" 탭 하단 "Privileged Gateway Intents"** 에서 **"Message Content Intent" 를 ON** → Save
   - ⚠️ 이걸 안 켜면 토큰·초대가 전부 정상이어도 **봇이 서버 채널 메시지 내용을 못 읽어** 무반응이 됩니다 (DM 은 예외적으로 읽힘). "토큰은 valid 한데 채널에서 답이 없다" 의 1순위 원인.
   - (선택) 멤버 목록 조회가 필요하면 "Server Members Intent" 도 ON.
4. OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: Send Messages / Read Messages / Read Message History / Add Reactions / Attach Files / Embed Links
5. 생성된 URL 로 봇을 본인 Discord 서버 / DM 가능 채널에 초대
6. (권장) 봇이 보일 채널 제어: 첫 봇이면 **DM 전용**이 가장 단순 — 서버에 초대하되 DM 으로만 대화. 특정 채널만 쓰려면 비공개 채널을 만들어 봇을 그 채널에만 추가.

> ⚠️ **봇마다 별도 초대 필수**: 봇은 각자 독립 Discord 앱이라 OAuth 초대도 봇 앱마다
> 따로. 다봇 셋업에서 신규 봇 초대를 빠뜨리면 그 봇만 무반응 (로컬 설정은 정상인데
> 인바운드 0건이면 1순위 = 미초대). 진단: [docs/08-debug-노하우.md J-3](../docs/08-debug-노하우.md).

### Step 4. 봇 토큰 입력 (AskUserQuestion + .env 저장)

agent 가 사용자에게 토큰 입력 요청. 다음 위치 저장:

```bash
cat > "$BOT_DIR/.env" <<EOF
DISCORD_BOT_TOKEN=<입력 토큰>
EOF
chmod 600 "$BOT_DIR/.env"
```

⚠️ 토큰 Discord 본문 / git / screenshot 노출 X.

### Step 5. soul.md template 선택 + 채우기

agent 가 다음 5 template 중 사용자 선택 안내:

| template | 적합 |
|---|---|
| `general-assistant` | 범용 비서 (default) |
| `research-bot` | 자료조사·교차검증 |
| `writing-bot` | 글쓰기·퇴고 |
| `schedule-bot` | 일정·Todo |
| `custom` | 자유 페르소나 |

선택 후 `<plugin>/templates/soul-<type>.md` 를 `$BOT_DIR/soul.md` 로 복사 + 다음 placeholder 대체:

- `<bot-name>` → 사용자 입력 봇 이름
- `<역할>` / `<어휘>` / `<시그니처>` 등 — AskUserQuestion 으로 받아 채우기

```bash
# thiscode plugin 위치 detect (templates/ 보유 위치) — PLUGIN_DIR 미설정 시.
# install-hooks.md 와 동일 후보 순서 (finding A 재발방지: 한 곳만 detect 하지 말 것).
if [ -z "${PLUGIN_DIR:-}" ] || [ ! -d "$PLUGIN_DIR/templates" ]; then
  for _cand in \
    "$HOME/.claude/plugins/marketplaces/thiscode-marketplace" \
    "$HOME/.claude/plugins/thiscode" \
    "$HOME/.claude/plugins/cache/local/thiscode" \
    "$HOME/code/thiscode" \
    "$HOME"/.claude/plugins/cache/thiscode-marketplace/thiscode/*; do
    if [ -d "$_cand/templates" ]; then PLUGIN_DIR="$_cand"; break; fi
  done
fi
if [ -z "${PLUGIN_DIR:-}" ]; then
  echo "❌ thiscode templates/ 못 찾음 — plugin install (또는 git clone) 먼저"
  exit 1
fi

TEMPLATE="$PLUGIN_DIR/templates/soul-${SOUL_TYPE}.md"
[ -f "$TEMPLATE" ] || TEMPLATE="$PLUGIN_DIR/templates/soul-general-assistant.md"

# placeholder 대체 (sed)
sed -e "s|<bot-name>|${BOT_NAME}|g" \
    -e "s|<YYYY-MM-DD>|$(date +%Y-%m-%d)|g" \
    -e "s|<역할 + 색깔 한 두 줄>|${ROLE_DESC}|g" \
    "$TEMPLATE" > "$BOT_DIR/soul.md"
```

사용자가 더 세밀한 customization 필요시 agent 가 Edit 도구로 추가 수정 안내.

### Step 6. WD (Working Directory) 결정 + CLAUDE.md 생성 (선택)

봇의 작업 디렉토리. 사용자 입력:

```
봇 WD (default: $HOME/<bot-name>/): 
```

agent 가 WD 안 `CLAUDE.md` 생성 (메타 + soul.md reference):

```markdown
# <bot-name> WD

> 본 디렉토리는 <bot-name> 봇의 작업 공간.
> Session 시작 시 `~/.claude/channels/discord-<bot-name>/soul.md` 자동 inject (SessionStart hook).

## 봇 메타

| 항목 | 값 |
|---|---|
| 봇 이름 | <bot-name> |
| 역할 | <역할> |
| Discord channels | discord-<bot-name> |
| Working Directory | <WD> |
```

### Step 7. claude 시동 안내

```bash
echo ""
echo "✅ 봇 디렉토리 생성 완료: $BOT_DIR"
echo ""
echo "다음 step — claude 시동:"
echo ""
echo "  export DISCORD_STATE_DIR=\"$BOT_DIR\""
echo "  cd <봇 WD>"
echo "  claude"
echo ""
echo "tmux session 안에서 운영 권장:"
echo "  tmux new-session -s ${BOT_NAME}"
echo "  export DISCORD_STATE_DIR=\"$BOT_DIR\""
echo "  cd <봇 WD>"
echo "  claude"
echo ""
echo "첫 대화 검증:"
echo "  Discord 앱에서 봇에 DM → 페어링 코드 발급 → 페어링 → 첫 응답"
```

---

## 검증

- [ ] `$BOT_DIR/.env` 존재 + chmod 600
- [ ] `$BOT_DIR/soul.md` 존재 + frontmatter `name = <bot-name>` 정확
- [ ] claude 시동 + DISCORD_STATE_DIR export 후 첫 응답에 페르소나 어휘 자연 포함
- [ ] Discord DM → 봇 응답 ✅

---

## 트러블슈팅

| 증상 | 원인 | 대응 |
|---|---|---|
| `permission denied` on .env | chmod 미적용 | `chmod 600 "$BOT_DIR/.env"` |
| Discord 봇 토큰 invalid | 줄바꿈 포함 또는 reset 후 미저장 | 토큰 재 발급 + .env 한 줄 |
| 토큰 정상인데 서버 채널에서 무반응 (DM 은 됨) | Message Content Intent OFF | Developer Portal → Bot → Privileged Gateway Intents → Message Content Intent ON |
| 페어링 코드 만료 | 봇에 다시 DM | 새 코드 발급 |
| soul.md 안 inject | DISCORD_STATE_DIR 미export 또는 SessionStart hook 미등록 | `/thiscode:install-hooks` 먼저 실행 |
| 같은 봇 이름 디렉토리 충돌 | 이미 존재 | 다른 이름 또는 기존 정리 |

---

## 관련 자원

- hook 등록: [install-hooks.md](install-hooks.md) — 반드시 본 명령 전에 실행
- DISCORD_STATE_DIR 구조: [../templates/discord-state-dir-README.md](../templates/discord-state-dir-README.md)
- soul.md template: [../templates/soul-general-assistant.md](../templates/soul-general-assistant.md)
- 메인 wizard: [start.md](start.md)
