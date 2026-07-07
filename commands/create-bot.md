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

### Step 0. 사용자 인터뷰 (USER-PROFILE 게이트 — 봇 설정보다 먼저)

**`~/.claude/USER-PROFILE.md` 가 이미 있으면 이 Step 을 건너뛰고 그 파일을 Read 해 Step 5·6 의 입력으로 쓴다.** 없으면 봇 설정 질문에 앞서 사용자를 인터뷰한다 — 봇 구성은 이 답에서 유도되는 결과물이지, 인터뷰의 본론이 아니다.

먼저 한 문장으로 고지: "봇을 만들기 전에 몇 가지 여쭙겠습니다 — 당신이 무슨 일을 어떻게 하는지 알아야 시스템이 당신에게 맞게 굽어집니다 (10분 정도)."

**앵커 질문 6종 — 대화형으로 진행한다. AskUserQuestion 의 보기 클릭이 아니라 자유 서술을 받고, 각 답변에 되묻기 1~2개(왜? 어떤 상황에서? 최근 실제 사례 하나만?)를 이어간다** (정본 스펙: user-profile-interview-design):

| # | 앵커 | 되묻기 예시 |
|---|---|---|
| A | 요즘 시간을 가장 많이 쓰는 일 2~3가지는? 각각 주당 몇 시간쯤? | 그중 가장 부담스러운 건? 왜? |
| B | 그중 하나를 시작→끝 순서로 얘기해 달라 (도구·산출물 포함) | 손으로 옮기는 단계가 있나?(복붙·정리·변환) |
| C | 그 흐름에서 제일 지겹거나 막히는 지점은? **최근 실제로 짜증 났던 일 하나** | 그때 얼마나 걸렸나? 없었으면 뭘 했을까? |
| D | 매주 반복하는 일 중 "기계가 해도 될 텐데" 싶은 것? | 안 맡기는 이유는?(신뢰? 방법?) |
| E | 자료를 어디에 모으고 어떻게 다시 찾나? **못 찾아서 다시 만든 적**은? | 주로 어떤 형태?(글·링크·PDF·대화) |
| F | 3개월 뒤 이 시스템이 해줬으면 하는 것 딱 하나는? | 그게 되면 시간이 얼마나 돌아오나? |

산출: `~/.claude/USER-PROFILE.md` 에 Write —

```yaml
---
schema_version: user-profile-v1
interviewed: <오늘 날짜>          # 재인터뷰 = 90일 경과 or 사용자 요청
completeness: full | partial      # 중간 이탈 허용 — 부분이면 partial
roles: []                         # A
workflows: []                     # B
pain_points: []                   # C — 구체 사례 포함
automation_wishes: []             # D
info_flow: {}                     # E
north_star: ""                    # F
---
(본문 = 인터뷰 대화 요약 산문 — 되묻기 답변의 뉘앙스 보존)
```

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

### Step 4.5. 페르소나·직무 프롬프트 고도화 (`/prompt` 연동 — 설치 권장)

Step 5/6 에서 placeholder 를 사용자 답변 그대로 박지 말고, 먼저 프롬프트 엔지니어링 패스를 한 번 돌린다:

- **`/prompt` 스킬이 설치돼 있으면 (권장)**: `/prompt --batch "봇 페르소나·직무 시스템 프롬프트 생성: 이름=<bot-name>, 역할=<Step0 roles 요약>, 업무 맥락=<north_star·pain_points 요약>, 산출=soul.md 의 역할/어휘/시그니처 절 + CLAUDE.md 의 업무 컨텍스트 절"` 을 실행해 고도화된 페르소나 프롬프트를 받고, 그 산출을 Step 5 placeholder 와 Step 6 구조에 주입한다. (에이전트 목적 감지 → 전문가 프라이밍·구조화가 자동 적용된다.)
- **미설치면**: 이 단계를 건너뛰고 AI 자체 생성으로 대체한다 — 단 사용자에게 한 줄 안내: "prompt-engineering 스킬을 설치하면 봇 페르소나 품질이 올라갑니다."

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
- **USER-PROFILE 소비 (Step 0 산출 — 보조층)**: ①template 추천 — `roles`/`pain_points` 에서 유도해 "당신 업무엔 research-bot 이 맞아 보입니다" 근거와 함께 제안 ②soul.md 말미에 `## 사용자 컨텍스트` 절(응답 톤 보정용 요약 2~3줄). **프로필의 본 정착지는 여기가 아니라 Step 6 의 구조(CLAUDE.md·폴더·rules·hook 후보)다** — soul 주입만 하고 끝내지 말 것.

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

> **USER-PROFILE 의 본 정착지 (구조 층)** — 인터뷰 답은 페르소나가 아니라 *구조*로 내려간다:
>
> | 프로필 필드 | 이 Step 에서 하는 일 |
> |---|---|
> | `north_star` | 생성하는 CLAUDE.md **최상단에 목표 1줄** ("이 시스템은 <north_star> 를 위해 있다") |
> | `roles` + `automation_wishes` | CLAUDE.md 에 `## 사용자 업무 컨텍스트` 절 — 모든 세션이 읽는 정본 층 |
> | `workflows` | **폴더 스캐폴드 제안** — 업무 흐름 순서대로 WD 하위 트리를 제안하고 동의 시 생성 (강의 업무면 `강의/`, 리서치면 `Research/` — 답변에 나온 실제 단계·산출물 이름을 쓴다, 범용 템플릿 ❌) |
> | `pain_points` | WD `rules/` 스캐폴드 — **페인포인트 1개 = rules/INDEX.md 트리거 행 1 + rule stub 1** ("복붙 정리에 시간 뺏김" → 저장 자동화 rule). 반복 실수형이면 **hook 후보를 1줄 제안**만 하고 사용자 판단에 맡긴다 (설치 시점 훅 강제 ❌) |

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
