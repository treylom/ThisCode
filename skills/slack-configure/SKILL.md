---
name: slack-configure
description: Use when connecting a new (or additional) Claude Code session to Slack via the claude-channel-server bridge. Automates Slack CLI auth, manifest file generation, bridge install, .env token capture, .mcp.json registration, and resident server startup end-to-end — pausing only at the 4 gates a human must click (CLI login, web app-creation from manifest + install approval, token paste, first-channel-load confirm), plus one conditional 5th gate (App Home message-tab toggle, only if the manifest didn't propagate it). App creation goes through Slack's web manifest flow — the CLI create/sync/install path is retired (TTY-only prompts, experiment flag, circular deps; 2026-08-06 WSL live test). This is the Slack counterpart of create-bot for Discord. Code-side half referenced as `/slack:configure` in claude-channel-server/src/config.ts:11,39.
disable-model-invocation: true
allowed-tools: Bash Read Write AskUserQuestion
---

사용자가 이 스킬을 호출했다 — 아래 단계를 순서대로 지금 수행한다.

# /thiscode:slack-configure — Slack 봇 연결 자동 셋업

> create-bot(Discord 판)의 Slack 대응. claude-channel-server 브리지(공식 `claude/channel` MCP 프로토콜)를 Slack 워크스페이스에 얹어, Claude Code 세션이 Slack DM·채널 메시지를 받고 `reply` 도구로 답할 수 있는 상태까지 만든다. 프로토콜·아키텍처·보안 모델·트러블슈팅의 기술 참고서는 [../slack-bridge/SKILL.md](../slack-bridge/SKILL.md) — 본 스킬은 그 설치·설정을 **자동 수행하는 실행기**다.

$ARGUMENTS

---

## 원칙 (2026-08-06 결정, 원문 인용)

> "무조건 자동으로 최대한 되게 하고, 수동으로 하거나 막히는 지점, 단계별로 할 게 있으면 사용자에게 질문하거나 가이드를 주는 방식이어야 합니다."

사람이 실제로 클릭·입력해야 진행되는 지점(**사용자 관문**)에서만 멈춰 안내하고 기다린다. 그 외 전부 자동 실행 — 매 단계 확인을 묻지 않는다.

## create-bot과 공유하는 부분

Step 0(USER-PROFILE 인터뷰)·페르소나 템플릿 선택 UX(Step 5)·시그니처 코퍼스 수집(Step 5-A)은 [create-bot](../create-bot/SKILL.md)과 **동일 로직**이라 그대로 재사용한다.

🔴 **WD/CLAUDE.md 생성은 재사용하지 않는다(2026-08-06 정정 — ㉡ 인격·거버넌스 이식)**: create-bot Step 6이 만드는 CLAUDE.md는 WD가 **선택**이고, 페르소나 주입은 `DISCORD_STATE_DIR` 기반 SessionStart 훅(`bot-session-init.sh`)에 의존한다. 그 훅은 Slack 상태 디렉토리(`CLAUDE_CHANNEL_SLACK_DIR`)를 인식하는 조건이 없어 — 인자도 `DISCORD_STATE_DIR`도 없으면 **무음 종료**(`exit 0`)한다 — Slack 세션에서는 파일만 있고 페르소나가 한 줄도 안 들어간다. 그래서 Slack 판은 WD를 **필수**로 만들고(D-2 확정 — 재경님 DM `1534838364`, `04-handoff.md` §2), 페르소나를 훅이 아니라 **CLAUDE.md 본문에 직접** 박아 넣는 **Step 7-A**를 아래에 새로 정의한다 — cwd 체인로드는 훅 등록 여부와 무관하게 항상 동작하기 때문이다.

본 스킬은 그 외에 create-bot Step 3(앱 생성)·Step 4(토큰 입력)·Step 6.7(연결 게이트)·Step 7(시동)에 대응하는 **Slack 판**만 새로 정의한다.

구조적 차이 1가지: Discord는 "봇 1개 = 앱 1개 = 프로세스 1개"지만, Slack 신아키텍처는 **"Slack 앱(워크스페이스 연결) 1개를 상주 `server.ts`가 쥐고, 그 위에 Claude Code 세션(=역할·봇) 여러 개가 `mcp.ts` 프록시로 붙는"** 구조다(`claude-channel-server/README.md:14`). "새 봇을 하나 더 만든다"가 Slack에선 "새 Slack 앱을 하나 더 만든다" 또는 "기존 앱에 세션을 하나 더 붙인다" 두 갈래로 갈린다 — 아래 입력 계약 1번에서 분기.

## 입력 계약 (착수 전 확인)

| # | 물을 것 | 질문 문구 |
|---|---|---|
| 1 | 신규 앱 vs 기존 앱 재사용 | "새 Slack 앱을 만들까요, 아니면 기존 앱(예: 클로드토푸)에 이 세션을 추가로 연결할까요?" |
| 2 | (신규 시) 봇 표시 이름 | "Slack에 표시될 봇 이름을 정해주세요 (예: 클로드토푸)." — **Slack UI 표시용**. 폴더명·CLAUDE.md 봇 메타에 쓰는 슬러그(`$BOT_NAME`)는 Step 0-A에서 별도로 확정한다(둘이 달라도 동작엔 지장 없음, 같게 두면 추적이 쉬움) |
| 3 | 워크스페이스 선택 | (`slack auth list` 결과가 여럿일 때만) "다음 중 어느 워크스페이스에 설치할까요?" — 하나뿐이면 자동 확정 후 확인만 |
| 4 | 채널 | "봇이 대화할 채널을 정해주세요 — 기존 채널 이름(`#example`) 또는 '새로 만들기'." |
| 5 | 페르소나/soul.md | "이 봇에 페르소나(성격·말투)를 입힐까요? create-bot과 같은 5종 템플릿(범용비서/자료조사/글쓰기/일정/커스텀) 중 고르거나 건너뛸 수 있습니다." — 질문 UX는 create-bot Step 5(+커스텀 모티브면 Step 5-A) 재사용, **실행은 아래 Step 0-A/7-A**(WD/CLAUDE.md 생성 메커니즘이 Slack 전용으로 다르다 — 위 "create-bot과 공유하는 부분" 참고) |
| 6 | 허용 사용자 ID | (자동 제안 후 확인만) "이 Slack 계정(`slack auth list`에서 확인된 User ID)만 봇과 대화하도록 설정할까요? 다른 사용자 ID를 쓰시려면 알려주세요." |

---

## 진행 흐름

### Step 0. 전제 확인 — 브리지 소스 위치 확정 + 자동 빌드 [자동 확인 + 자동 빌드 + 조건부 폴백]

`claude-channel-server` 소스는 **ThisCode 번들에 `vendor/claude-channel-server/`로 동봉되어 있다**(2026-08-06 vendor 동봉 결정) — 이 경로가 기본값이다. 동봉된 건 소스뿐이고 `dist/`(빌드 산출물)는 없다(`.gitignore` 제외 — 소스↔빌드본 drift 방지). 그래서 Step 0은 경로 확인 다음에 **빌드까지 자동으로** 끝낸다.

**① 경로 확인 [자동]**:

```bash
# 기본: ThisCode 번들 내 vendor 경로
BRIDGE_SRC="<ThisCode 설치 경로>/vendor/claude-channel-server"
test -d "$BRIDGE_SRC" && echo "found: bundled vendor path" || echo "not found — 폴백 확인 필요"
```

번들 경로가 있으면 그대로 쓰고 자동으로 다음 단계(빌드)로 진행한다 — 사람에게 묻지 않는다.

**② 폴백 [조건부, 사람 관문 아님 — 사용자가 먼저 밝힌 경우만]**: 사용자가 번들 경로 대신 다른 위치의 체크아웃을 쓰고 싶다고 밝히면(예: 로컬 fork로 작업 중) 그 경로를 물어 `$BRIDGE_SRC`를 그 값으로 대신 쓴다: "다른 위치의 `claude-channel-server` 체크아웃을 쓰시려면 경로를 알려주세요 — 없으면 번들 경로(`vendor/claude-channel-server/`)를 그대로 씁니다." 번들 경로도 없고 폴백 경로도 못 찾으면 여기서 멈춘다(레포가 손상된 상태 — 정상 배포본이라면 발생하지 않는다).

**③ 자동 빌드 [자동]** — 경로가 확정되면 사람 관문 없이 바로 빌드한다(`package.json`에 이미 정의된 스크립트 한 줄, `slack-bridge/SKILL.md` 전제 절과 동일 계약):

```bash
cd "$BRIDGE_SRC"
npm install && npm run build
```

- **성공**(exit 0, `dist/server.js`·`dist/mcp.js` 존재 확인) → 그대로 Step 1로 자동 진행.
- **실패**(exit ≠ 0) → **여기서 멈춘다.** 안내 문구: "브리지 빌드에 실패했습니다(`npm install` 또는 `npm run build` 단계). 아래 에러를 확인해 주세요:\n\n<stderr 마지막 20줄>\n\n먼저 Node 버전(`node -v` ≥ 20)과 네트워크 연결(npm 레지스트리 접근)을 점검해 주세요. 여기서 안 잡으면 나중에 resident server 기동(Step 13) 단계에서 `dist/server.js`가 없어 원인 불명 에러로 나타납니다 — 그래서 이 단계에서 먼저 확인합니다." 빌드가 실패한 채로 이후 Step으로 넘어가지 않는다.

### Step 0-A. 봇 이름·페르소나 선택 — ㉡ 인격·거버넌스 이식 착수 [사용자 관문]

> create-bot(Discord 판) Step 1(봇 이름)·Step 5(페르소나 템플릿)와 **같은 질문 UX**를 여기서 먼저 받는다. 뒤의 **Step 7-A**(봇 루트 폴더 생성)가 이 값을 그대로 쓴다 — 순서를 건너뛰면 Step 7-A가 멈춘다.

**질문 1 — 봇 이름(슬러그)**: "봇 이름을 정해주세요 (영문 소문자+하이픈, 예: slack-assistant) — 폴더 이름과 CLAUDE.md 봇 메타에 그대로 쓰입니다." 검증: `^[a-z][a-z0-9-]*$`, 1-32자. → `$BOT_NAME`

**질문 2 — 역할 한 줄**: "이 봇이 주로 하는 일을 한 줄로 알려주세요 (예: 자료조사·교차검증)." → `$ROLE_DESC`

**질문 3 — 페르소나 템플릿**(입력 계약 #5와 동일 문구): "이 봇에 페르소나(성격·말투)를 입힐까요? 범용비서(general-assistant, 기본값) / 자료조사(research-bot) / 글쓰기(writing-bot) / 일정(schedule-bot) / 커스텀(custom) / 건너뛰기 중 골라주세요." → `$SOUL_TYPE`(건너뛰면 `general-assistant` 기본값 — "페르소나 없이도 진행되지만, Step 7-A가 만드는 CLAUDE.md는 기본 비서 톤으로 채워집니다" 안내).

커스텀(모티브 있는 페르소나)을 골랐으면 **create-bot Step 5-A(시그니처 코퍼스 수집)를 여기서 그대로 수행**한 뒤 그 산출을 `$SOUL_TYPE=custom`과 함께 다음 단계로 넘긴다.

값 보존(이후 단계가 다른 셸 실행일 수 있으므로 — Step 8의 `STATE_DIR` 포인터와 동일 이유):

```bash
mkdir -p "$HOME/.claude/channels"
printf '%s\n' "$BOT_NAME"  > "$HOME/.claude/channels/.slack-configure-bot-name"
printf '%s\n' "$SOUL_TYPE" > "$HOME/.claude/channels/.slack-configure-soul-type"
printf '%s\n' "$ROLE_DESC" > "$HOME/.claude/channels/.slack-configure-role-desc"
```

### Step 1. 사전 점검 + Slack CLI 자동 설치 [자동] (F1 — 2026-08-06 루돌프 WSL round 1 실측 반영)

> 🔴 **실측**: 신규 WSL 환경에서 `slack --version` → `command not found`. 번들 어디에도(README·`install.sh`·트러블슈팅 표) 설치 방법이 없었다 — Step 0(브리지 빌드)은 실패 시 상세 안내가 있는데(위 참고) Step 1은 같은 대접이 없는 비대칭이었다. 아래가 그 비대칭을 없앤다.

```bash
node -v   # ≥20 (claude-channel-server/package.json engines.node)

if command -v slack >/dev/null 2>&1; then
  echo "✅ slack CLI 이미 있음: $(slack --version)"
else
  echo "ℹ️  slack CLI 미발견 — 자동 설치를 시도합니다(sudo 불필요, 홈 디렉토리 설치)."
fi
```

**Slack CLI 자동 설치 [자동, sudo 0]** — `slack` 명령이 없을 때만 실행한다.

🔴 **패키지 매니저(apt/dnf/`sudo` 동반 설치) 경유로 짜지 않는다** — 대상 환경이 무-sudo일 수 있다(2026-08-06 루돌프 WSL 실측: `sudo -n true` → `a password is required`, round 2에서 sudo 경로는 관문 앞에서 그대로 탈락한다). 공식 설치 스크립트는 sudo를 요구하지 않는다 — 문서 전문에 "sudo"라는 단어가 한 번도 등장하지 않고, 기본 설치 경로 자체가 홈 디렉토리다(`$HOME/.slack`에 다운로드 후 `$HOME/.local/bin`에 심볼릭 링크 — 2026-08-06 공식 문서 확인: [Installing the Slack CLI for Mac & Linux](https://docs.slack.dev/tools/slack-cli/guides/installing-the-slack-cli-for-mac-and-linux/)):

```bash
# 존재 판정은 두 자로: PATH + 실파일 — 비대화형 셸은 PATH 만으로 「미설치」 오판 → 불필요 재다운로드 (2026-08-08 WSL E2E 실측)
if ! command -v slack >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/slack" ]; then
  curl -fsSL https://downloads.slack-edge.com/slack-cli/install.sh | bash
fi
```

> codex 짝 = ThisCodex `skills/slack-bridge/SKILL.md` 0단계 (교차 갱신 계약 — 설치 공정·PATH 함정·실측 라벨은 양쪽 동시 반영).

⚠️ **설치가 성공해도 그 셸에서 바로 안 잡힐 수 있다** — 공식 문서 자인이었던 이 함정은 2026-08-08 클린룸 실측으로 재현 확인됐다(WSL2 · Ubuntu 24.04.1 · x86_64 · v4.6.0 — 설치 5초, 직후 새 셸에서 `slack` = not found. 설치기는 Required manual setup 으로 PATH 등록을 사람에게 미룬다). 그래서 재확인 + PATH 보정 + **영구 등록까지가 이 자동 단계다**(2026-08-08 재경님 결정 "slack cli 는 알아서 설치하도록 동봉" — 사람에게 남기던 등록 안내를 자동화로 승격). 블록 E2E 검증 급(2026-08-08 클린룸 WSL): 프로필 전무·전형 우분투 두 시나리오 각 2회 — 완주·재다운로드 0·새 셸 `-lc`/`-ic` 모두 잡힘:

```bash
export PATH="$HOME/.local/bin:$PATH"   # 현재 셸 보정 — 설치 여부와 무관(중복 무해)
if command -v slack >/dev/null 2>&1; then
  # 새 셸에서도 잡히게 영구 등록(중복 추가 없음)
  persisted=0
  for profile in "$HOME/.bashrc" "$HOME/.zshrc"; do
    [ -f "$profile" ] || continue
    grep -qs 'HOME/.local/bin' "$profile" || printf '\n# Slack CLI PATH (ThisCode slack:configure Step 1)\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$profile"
    persisted=1
  done
  if [ "$persisted" != 1 ]; then
    # 프로필 전무 환경: .profile(로그인 셸용)만 만들면 대화형 비로그인 셸(bash -ic)이 못 읽는다(실측 exit 127 —
    # 이때 우분투 command-not-found 가 «sudo snap install slack»[데스크톱 앱, CLI 아님]을 오권유) → 둘 다 기록
    for profile in "$HOME/.bashrc" "$HOME/.profile"; do
      grep -qs 'HOME/.local/bin' "$profile" || printf '\n# Slack CLI PATH (ThisCode slack:configure Step 1)\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$profile"
    done
  fi
fi

if command -v slack >/dev/null 2>&1; then
  echo "✅ slack CLI 설치/확인 완료: $(slack --version)"
else
  echo "❌ slack CLI 를 찾을 수 없습니다."
  echo ""
  echo "1. 네트워크 연결(downloads.slack-edge.com 접근)을 확인해 주세요 — 위 curl 자체가 실패했다면 그 에러가 원인입니다."
  echo "2. 위 자동 PATH 등록이 실패한 경우 — \$HOME/.local/bin 을 셸 프로필에 직접 등록해 주세요(예: ~/.bashrc):"
  echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo "   등록 후 새 셸을 열고 'slack --version' 을 다시 확인해 주세요."
  echo "3. 그래도 안 되면 수동 설치(sudo 불필요) — 공식 Linux 바이너리(.tar.gz, x86_64/ARM64)를 내려받아 \$HOME/.slack 에 풀고 \$HOME/.local/bin 에 심볼릭 링크를 만드는 절차가 공식 문서에 있습니다:"
  echo "     https://docs.slack.dev/tools/slack-cli/guides/installing-the-slack-cli-for-mac-and-linux/"
  echo ""
  echo "여기서 안 잡으면 이후 모든 Step(로그인·앱 생성·매니페스트 동기화)이 전부 'command not found' 로 막힙니다 — 그래서 이 단계에서 먼저 확인합니다."
  exit 1
fi

slack --version   # ≥4.x
```

> ⚠️ **sudo가 필요한 설치 경로(시스템 전역 패키지 매니저 등)는 이 [자동] 단계에 넣지 않는다** — 공식 문서 자체가 sudo 없는 홈 디렉토리 설치를 표준으로 제시하므로 이 스킬도 그 표준만 자동화한다. 사용자가 다른 방식(예: `brew`)으로 이미 설치해 뒀다면 첫 줄의 `command -v slack` 검사가 자동 설치를 건너뛴다. Deno 등 **런타임 설치는 이 CLI 설치 범위 밖**(공식 문서: "Runtime installations are left to the developer") — claude-channel-server는 Deno에 의존하지 않으므로 여기서 다루지 않는다.
>
> ⚠️ 이번 수리는 **설치 층**이다. (구 미결 #1 이 가리키던 "CLI 앱 생성 왕복"은 2026-08-06 WSL 실측으로 **경로 자체가 폐기**됐다 — Step 4 의 🔴 주석과 미결·리스크 절 참조. Slack CLI 는 이제 인증(관문 A)과 앱 ID 확보 후 비대화형 호출에만 쓴다.)

`claude-channel-server` 소스 위치는 Step 0에서 이미 확인했다.

### Step 2. 기존 인증 확인 [자동]

```bash
slack auth list
```

이미 로그인된 팀이 있으면 Step 3(관문 A)을 건너뛴다.

### Step 3. Slack CLI 로그인 — 관문 A [사용자 관문]

```bash
slack login --no-prompt
# 출력: /slackauthticket <티켓문자열>
```

> **안내 문구**: "Slack CLI 인증이 필요합니다.
> 1. 아래 뜬 코드(`/slackauthticket ...`)를 복사하세요.
> 2. Slack 앱에서 아무 채널에나 붙여넣고 Enter — 'Confirm' 버튼을 누르면 화면에 확인 코드가 표시됩니다(영숫자 — 2026-08-06 실측 8자리, 자릿수는 고정 아님).
> 3. 그 코드를 여기 붙여넣어 주세요.
> (이미 로그인돼 있으면 이 단계는 자동으로 건너뜁니다.)"

코드 수신 후:

```bash
slack login --no-prompt --ticket <티켓> --challenge <코드>
slack auth list   # 워크스페이스·User ID 나오면 성공 (~/.slack/credentials.json)
```

### Step 4. 매니페스트 파일 생성 [자동]

> 🔴 **CLI 앱 생성 경로(`slack create` → `manifest sync` → `app install`)는 폐기한다** — 2026-08-06 루돌프 WSL round 3 실측 4건: ①`--template blank` 은 존재하지 않는다(`template_path_not_found` — `-t` 는 `slack-samples/...` 레포 경로를 받는다) ②`slack manifest sync` 는 `--experiment manifest-sync` 플래그를 요구한다(실험 플래그 의존 = 수강생 배포물 부적합) ③sync 는 설치를 요구하고 install 은 원격 앱 선택을 요구하는 **순환**(`installation_required`) ④`slack app install` 은 `--environment local` 을 줘도 두 번째 대화형 프롬프트("Select an app")가 떠서 **TTY 없는 실행 맥락(이 스킬의 주체 = Claude 세션 Bash)에서 비대화형 진입점이 없다**. 앱 생성은 Slack 표준인 **웹 매니페스트 경로**(아래 Step 5)로 가고, 앱 ID 확보 후에만 CLI 비대화형(`--app <ID>`)이 성립한다.

이 단계는 아래 매니페스트 JSON 을 `<앱 이름>`·`<봇 표시 이름>` 만 Step 0-A 값으로 치환해 **파일로 떨군다**(예: `$HOME/.claude/channels/.slack-configure-manifest.json` — 비밀값 없음, [slack-bridge/SKILL.md](../slack-bridge/SKILL.md) 예시와 동일 정본):

```json
{
  "_metadata": {
    "major_version": 1,
    "minor_version": 1
  },
  "display_information": {
    "name": "<앱 이름 — 예: 클로드토푸 (한글 가능 — 사람이 보는 이름)>"
  },
  "features": {
    "app_home": {
      "home_tab_enabled": true,
      "messages_tab_enabled": true,
      "messages_tab_read_only_enabled": false
    },
    "bot_user": {
      "display_name": "<멘션 핸들 — 예: claudetofu. 🔴 영문 권장(ASCII) — 자동완성은 한글 표시명도 잡히지만(2026-08-07 재실측) 안 뜨는 사례(미초대·반영 직후)가 있어 이 영문 핸들이 확실한 경로. 기본값 = Step 0-A 의 $BOT_NAME>",
      "always_online": true
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "chat:write",
        "im:history",
        "channels:history",
        "app_mentions:read",
        "reactions:write"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_home_opened",
        "app_mention",
        "message.channels",
        "message.im"
      ]
    },
    "interactivity": {
      "is_enabled": false
    },
    "org_deploy_enabled": true,
    "socket_mode_enabled": true,
    "token_rotation_enabled": false
  }
}
```

핵심(DM·멘션이 실제로 되게 하려면 **필수**): `messages_tab_enabled: true` · `bot_events`에 `message.im`/`message.channels`/`app_mention` 전부 · 스코프 `chat:write`/`im:history`/`channels:history`/**`app_mentions:read`**(빠지면 `invalid_manifest` — `app_mention` 이벤트가 이 스코프를 요구, 2026-08-06 실측)/`reactions:write`(이모지 반응 도구 — 2026-08-06 재경님 요청) · `socket_mode_enabled: true`.

### Step 5. 앱 생성 + 워크스페이스 설치 — 관문 B [사용자 관문 / 조건부 자동화 대행]

**진입 시 선택 질문**(재경님 설계 지시 2026-08-06 — "브라우저 자동화로 하게 하거나, 직접 하게 하거나 선택지를 주는 방향"):

> "브라우저 작업을 제가 대신 할까요, 직접 하시겠습니까?
> ① **제가 진행** — 브라우저 자동화로 앱 생성·설치 클릭을 대신합니다. 단 **Slack 로그인 화면이 뜨면 그때만 직접** 해주셔야 합니다(자동화의 상한 — 로그인 세션은 사람 몫입니다).
> ② **직접 진행** — 아래 4단계를 따라 하시고 App ID 만 알려주세요."

- ①은 **이 세션에서 실제로 쓸 수 있는 브라우저 자동화 도구가 있을 때만 제안**한다 — 특정 이름(`/chrome` 등)으로 못 박지 말 것: 환경마다 다르다(2026-08-06 WSL 실측: `/chrome` 부재·playwright MCP 가용). 가용 도구가 하나도 없으면 선택 질문 없이 ②만 안내한다.
- ① 경로의 범위 = 아래 안내 4단계 전체(매니페스트 붙여넣기 → Create → Install to Workspace → 허용 → App ID 읽기). 완료 후 App ID 를 사용자에게 보여주고 확인받는다.

🔴 **안내 시 매니페스트 전문을 대화창에 코드블록으로 직접 출력한다(1순위)** — "클립보드에 복사해 뒀습니다"나 파일 경로만 주는 방식 금지. 클립보드는 눈에 안 보이는 저장소고 파일 열기는 또 하나의 관문이다(2026-08-06 재경님 라이브 지적 — "클립보드에 있다고 하면 모르는 사람 있어, 출력해주던가 해야 해"). 클립보드 복사·파일 경로는 **보조로 병기**만 한다. 일반 원칙: **스킬이 사람에게 뭘 시킬 때는 그 사람이 화면에서 바로 볼 수 있는 형태로 준다** — 관문 D(토큰 안내)에도 동일 적용. 확장(2026-08-06 결함 11): ①UI 위치 지시("메뉴 X → 스크롤 Y")보다 **URL·명령·복사 가능한 식별자**를 우선한다 — UI 는 Slack 이 바꾸면 문서가 조용히 낡지만 URL 구조·명령은 오래 산다(사례: 채널 ID = 세부정보 탭 위치 안내 실패 → 링크 복사로 교체, Step 9) ②모든 사용자 관문 안내 끝에 **"화면이 이 안내와 다르면 그 자리에서 알려달라"** 한 줄을 붙인다 — 사용자가 막힌 채 포기하는 것이 최악 경로다.

> **② 직접 진행 안내 문구**: "이제 브라우저에서 Slack 앱을 만듭니다(약 1분, 붙여넣기 한 번).
> 1. https://api.slack.com/apps 접속 → 우상단 **Create New App** → **From an app manifest** 선택.
> 2. 워크스페이스를 고르고, **아래에 출력해 드린 매니페스트 내용을 통째로 복사**해 JSON 탭에 붙여넣기 → **Create**.
> ```json
> (여기에 매니페스트 전문을 그대로 출력)
> ```
> (같은 내용이 클립보드에도 복사돼 있고, 파일로도 `<매니페스트 파일 경로>` 에 있습니다 — 편한 쪽을 쓰세요.)
> 3. 왼쪽 메뉴 **Install App** → **Install to Workspace** → **승인 화면의 권한 목록에 5줄이 보이는지 확인**해 주세요 — 메시지 보내기(chat:write)·DM 기록 보기(im:history)·채널 기록 보기(channels:history)·멘션 읽기(app_mentions:read)·반응 달기(reactions:write). **줄 수가 모자라면 매니페스트가 덜 반영된 것입니다 — 허용을 누르지 말고 알려주세요**(여기서 잡으면 재설치 왕복이 없습니다). 5줄이 맞으면 초록색 **허용(Allow)**.
> 4. 왼쪽 **Basic Information** 상단의 **App ID**(`A`로 시작)를 알려주세요."

🔴 **한 번에 안내 원칙** (2026-08-06 재경님 지시 — "스킬 사용 시 한 번에 안내가 되어야 하는데 말이죠"): 위에서 출력하는 매니페스트가 **최종 완결본**이다 — scope·이벤트 구독·설정 전부 포함이며, 이후 어느 단계에서도 권한·설정을 추가로 요구하지 않아야 정상이다. 그래서 3번의 승인 화면 «5줄 확인»이 왕복을 선제로 없애는 자리다(라이브 실측 2026-08-06 결함 15: 선언은 온전했는데 **갱신 후 재설치가 빠져** 부여가 옛것 그대로였고, DM 이 무징후로 죽었다 — 매니페스트 갱신 ≠ 재설치).

**매니페스트 «갱신» 경로 (앱이 이미 있을 때 — 결함 16 처방)**: 이미 만든 앱의 scope·이벤트를 바꿀 때는 브라우저 UI 안내를 다시 밟게 하지 않는다 — 한국어 화면("범위"=Scopes)·스크롤·"이미 있는 항목은 추가 목록에 안 뜸" 함정이 전부 그 화면에 산다(2026-08-06 재경님 라이브 적발). 대신:
1. **API 직행(1순위)**: 관문 A 를 지났으면 `~/.slack/credentials.json` 에 config token(`xoxe.`)이 있다 → `apps.manifest.export` 로 현재본 백업 → 갱신본으로 `apps.manifest.update`(⚠️ **전체 교체**라 부분 패치 아님 — export 본에 델타를 적용한 완성본을 넣는다) → 재확인. 토큰 값은 출력하지 않는다.
2. 갱신이 어느 경로로 됐든 **scope 가 늘었으면 재설치 필수** — `api.slack.com/apps/<APP_ID>/install-on-team` URL 직행으로 안내(라벨 대신 URL, 라벨을 쓸 땐 한/영 병기 — "범위(Scopes)"). ⚠️ **동의 화면은 캐시된다**(2026-08-06 라이브 실측: 매니페스트 갱신 전에 열려 있던 탭으로 재설치하니 옛 권한 목록 그대로 승인돼 부여가 안 늘었다 — 재설치 왕복 +1). 안내문에 반드시: **"링크는 새로고침(또는 새 탭)으로 열고, 동의 목록에 방금 추가한 권한이 보이는지 눈으로 확인한 뒤 허용을 누르세요 — 안 보이면 누르지 말고 알려주세요"**(눌러버리면 원인이 묻힌다). 재설치로 토큰이 회전될 수 있으니 직후 Step 10-c(부여 대조)를 재실행하고, 회전됐으면 관문 D 재캡처.
3. "추가하세요"류 지시를 출력하기 **전에 현재 상태를 먼저 읽는다**(export or 승인 화면 줄 수) — 이미 선언돼 있으면 그 단계는 건너뛰고 재설치만 안내한다.

App ID 를 받으면 이후 CLI 호출이 필요할 때 `--app <ID>` 로 비대화형이 성립한다. (검증: `slack auth list` 는 이미 통과 상태 — 앱 생성 자체는 CLI 확인 불요, 다음 관문 D 의 토큰 발급이 곧 생성 성공의 증거다.)

### Step 6′. (조건부) 메시지 탭 켜기 — 관문 C [사용자 관문, 조건부]

매니페스트의 App Home 설정이 반영되지 않아 DM 이 막혀 있을 때만 발동한다 — 평소엔 이 단계 자체가 안 뜬다.

> **안내 문구**: "DM이 아직 막혀 있는 것 같습니다. api.slack.com/apps → 방금 만든 앱 선택 → 왼쪽 메뉴 'App Home' → 아래로 스크롤해 'Show Tabs → Messages Tab' 섹션에서 토글을 켜주세요. 켠 뒤 Slack 앱을 새로고침하면 반영됩니다."

### Step 7. 브리지 설치 [자동]

```bash
cd claude-channel-server
npm install
npm run build
```

⚠️ `package.json`에 `postinstall`/`preinstall`/`prestart`가 의도적으로 없다(세션 시작마다 `npm install`이 트리거되는 걸 막기 위해서). 의존성은 정확한 버전으로 pin되어 있다.

### Step 7-A. 봇 루트 폴더 생성 — ㉡ 인격·거버넌스 이식 [자동]

> **D-2 확정 결정**(재경님 2026-08-06, DM `1534838364` — "우리의 ThisCode대로면, D-2가 맞죠"): Slack 응답 세션의 cwd는 수강생 워크스페이스(vault) 안 **봇 전용 루트 폴더**여야 하고, 그 폴더엔 반드시 자기 `CLAUDE.md`가 있어야 한다. 없으면 세션 기동 시 정체성 fallback이 워크스페이스 루트(그 위) CLAUDE.md의 봇 메타로 해소된다 — 오염 실측: `04-handoff.md` §3.4 "가드의 fallback 가지가 오염 문서를 정답으로 지목한다". Step 0-A에서 받은 `$BOT_NAME`·`$SOUL_TYPE`·`$ROLE_DESC`를 여기서 실제 파일로 굽는다.

**① 워크스페이스 루트 확정 + 폴더 생성**

```bash
BOT_NAME=$(cat "$HOME/.claude/channels/.slack-configure-bot-name" 2>/dev/null)
SOUL_TYPE=$(cat "$HOME/.claude/channels/.slack-configure-soul-type" 2>/dev/null)
ROLE_DESC=$(cat "$HOME/.claude/channels/.slack-configure-role-desc" 2>/dev/null)
[ -n "$BOT_NAME" ] || { echo "❌ Step 0-A가 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }

WORKSPACE_ROOT="$PWD"   # 이 스킬을 호출한 세션의 cwd = 수강생 워크스페이스(vault) 루트로 간주
BOT_DIR="$WORKSPACE_ROOT/${BOT_NAME}"

if [ -d "$BOT_DIR" ]; then
  echo "❌ $BOT_DIR 이미 존재 — 다른 봇 이름을 쓰거나 기존 폴더를 확인해주세요."
  exit 1
fi
mkdir -p "$BOT_DIR"

# 이후 단계(Step 12·13-A·15-A)로 값을 넘기는 방법 = 파일 포인터
# (Step 8의 STATE_DIR 포인터와 동일 이유 — 이 스킬의 bash 블록은 서로 다른 셸 실행일 수 있다).
printf '%s\n' "$BOT_DIR" > "$HOME/.claude/channels/.slack-configure-bot-dir"
echo "봇 루트 폴더: $BOT_DIR"
```

**② 페르소나 템플릿 채우기(create-bot Step 5와 동일 로직 재사용)**

```bash
# PLUGIN_DIR detect — create-bot Step 5와 동일 후보 순서(다른 곳 한 곳만 보지 않는다)
if [ -z "${PLUGIN_DIR:-}" ] || [ ! -d "$PLUGIN_DIR/templates" ]; then
  for _cand in \
    "$HOME/.claude/plugins/marketplaces/thiscode-marketplace" \
    "$HOME/.claude/plugins/thiscode" \
    "$HOME/.claude/plugins/cache/local/thiscode" \
    "$HOME/code/thiscode" \
    "$HOME"/.claude/plugins/cache/thiscode-marketplace/thiscode/* \
    "$HOME"/.claude/plugins/cache/*/thiscode/*; do
    if [ -d "$_cand/templates" ]; then PLUGIN_DIR="$_cand"; break; fi
  done
fi
[ -n "${PLUGIN_DIR:-}" ] || { echo "❌ thiscode templates/ 못 찾음 — plugin install (또는 git clone) 먼저"; exit 1; }

TEMPLATE="$PLUGIN_DIR/templates/soul-${SOUL_TYPE}.md"
[ -f "$TEMPLATE" ] || TEMPLATE="$PLUGIN_DIR/templates/soul-general-assistant.md"

sed -e "s|<bot-name>|${BOT_NAME}|g" \
    -e "s|<YYYY-MM-DD>|$(date +%Y-%m-%d)|g" \
    -e "s|<역할 + 색깔 한 두 줄>|${ROLE_DESC}|g" \
    "$TEMPLATE" > "$BOT_DIR/soul.md"
```

**②-b 잔여 자리표시자 채움 + Slack 맥락화 [자동 — 에이전트 작성 단계]**

🔴 위 sed 3종은 시작일 뿐이다 — 템플릿에는 자리표시자가 종류별로 12~19개 있고(2026-08-06 루돌프 WSL round 2 실측: general-assistant 15종 중 12종이 꺾쇠 stub 그대로 실려 **SOUL-CAPSULE 블록 통째가 속 빈 껍데기**가 됐다), 고정 sed 목록을 늘리는 방식은 템플릿이 바뀔 때마다 같은 병이 재발한다. 이 스킬의 실행 주체는 Claude 세션이므로 남은 자리는 **에이전트가 직접 채운다**:

0. 🔴 **조사 먼저 — 즉석 창작 금지** (2026-08-06 재경님 지시: "실제 스킬 사용때는 자료조사하고 vault조사하고 하면서 제대로 찾아야 합니다"): 자리를 채우기 **전에** 그 사용자의 실제 맥락을 근거로 수집한다 — ⓐ워크스페이스에 vault·노트가 있으면 검색(`/search`·knowledge-manager·grep)으로 실제 어휘·업무 영역·반복 작업을 훑고 ⓑ기존 봇 soul.md 들이 있으면 어휘·경계 규약을 대조하고 ⓒ둘 다 없는 환경(신규 사용자)이면 **사용자에게 짧은 인터뷰**(주 업무 2~3개·자주 쓰는 말투/단어·봇이 하면 안 되는 일 1개)로 받는다. `$BOT_NAME`·`$ROLE_DESC` 만 보고 지어내면 결과가 **일반 비서 톤으로 수렴**한다 — 같은 경고가 Discord 판에 이미 실측으로 박혀 있다(create-bot SKILL.md "실제 코퍼스를 먼저 수집" 절: 상상으로 채우면 어떤 모티브든 비슷한 비서 톤 수렴, 사용자가 "봇 특성을 못 살린다"고 느끼는 1순위 원인). 2026-08-06 WSL 라이브에서도 조사 없이 채운 캡슐이 "노트 정리를 갈무리해 돕는 일반 비서"로 수렴했다 — 그럴듯한 창작 ≠ 그 사용자의 실제 맥락.
1. **잔여 전수 나열**: `command grep -n '<[^>]*>' "$BOT_DIR/soul.md"`
2. **각 자리를 0번 조사 결과를 근거로 채운다**(Edit 도구) — `$BOT_NAME`·`$ROLE_DESC`·`$SOUL_TYPE` 맥락에 맞게. 특히 SOUL-CAPSULE 안의 `<페르소나 어휘 마커 1~3개>`·`<시그니처 1~3>`·`<경계 1줄>`·`<출력·언어 규약 1줄>`이 핵심이다 — 여기가 비면 "매 응답 자가 점검" 규율이 작동하지 않는다. **시그니처 이모지 1~3종**도 여기서 정한다(2026-08-06 재경님 요청 "각 봇별로 이모지 다르게") — 캡슐에 "반응(react)은 주로 `<이모지1>`·`<이모지2>` 를 쓴다" 1줄을 넣으면 봇마다 다른 이모지로 반응한다. 0번 조사 결과(그 사용자·봇 성격에 맞는 이모지)를 근거로 고른다. 단 **지어낼 수 없는 실 ID 계열**(`<@본인 봇 ID>` 등)은 날조하지 말고 `(Step 15-A에서 실측 기입)` 마커로 바꿔둔다.
3. **Slack 맥락화**: 템플릿은 Discord 판 공용이라 Discord 전용 문구가 남는다 — "Discord DM/mention 수신 시" → Slack 등가로, `mcp__plugin_discord_discord__reply` 도구 지시 → "Slack 응답은 `slack-channel` MCP reply 도구로만" 으로 치환. **Slack 봇에게 Discord 도구를 시키는 문장이 남으면 조용한 오작동을 유발한다**(루돌프 실측: 생성된 soul.md L83).
4. **기계 게이트**:

```bash
command grep -o '<[^>]*>' "$BOT_DIR/soul.md" | grep -v '^<@U' | grep -v '^<!--'
# 출력이 비어야 PASS
```

   허용 잔존 = 실 Slack ID(`<@U...>`)와 **HTML 주석**(`<!-- SOUL-CAPSULE-START -->` 같은 구조 마커 — 지우면 안 되는 정상 요소다). 그 외 꺾쇠가 하나라도 출력되면 이 단계 미완 — 채우고 다시 센다. ⚠️ 주석 예외 없이 `<[^>]*>` 만으로 재면 캡슐 마커 2줄이 항상 걸려 **게이트가 영원히 통과 불가**가 되고, 성실한 에이전트일수록 마커를 지우는 쪽(규율 위반)으로 유도된다 — 2026-08-06 루돌프 round 2.1 실측.

**③ CLAUDE.md 작성 — 페르소나를 훅이 아니라 본문에 직접 박는다** (반드시 ②-b 완료 후 — `$SOUL_BODY`는 완성본 soul.md를 읽는다)

🔴 **`soul.md` 본문(`$SOUL_BODY`)을 unquoted heredoc의 `${...}` 자리에 직접 넣지 않는다** — 5종 템플릿 전부 backtick(코드 스팬)을 5~12개씩 포함하고, Step 5-A 커스텀 코퍼스는 실제 대사·밈을 그대로 옮기므로 backtick·`$`가 더 나올 수 있다. unquoted heredoc은 그걸 command substitution으로 오인해 내용이 깨진다 — 그래서 아래는 **① 고정 헤더는 quoted heredoc(변수 미확장) + sed 치환**, **② soul 본문은 `printf`로 그대로 append**(쉘 재해석 없음) 두 단계로 나눈다:

```bash
AGENTS_IMPORT=""
if [ -f "$WORKSPACE_ROOT/AGENTS.md" ]; then
  AGENTS_IMPORT='@../AGENTS.md'
fi
SOUL_BODY=$(cat "$BOT_DIR/soul.md")

cat > "$BOT_DIR/CLAUDE.md" <<'HEADER_EOF'
# __BOT_NAME__ — Slack 봇 WD

> 이 디렉토리는 **__BOT_NAME__** 봇의 작업 디렉토리(WD)다. Slack 응답 세션은 반드시 이 폴더를 cwd로 기동한다(`/thiscode:slack-configure` Step 13-A — 현행 「빈 session/ 폴더」 방식은 폐기).
> **왜 soul.md를 훅이 아니라 이 파일 본문에 직접 넣나**: Discord 판(create-bot)의 페르소나 주입은 `DISCORD_STATE_DIR` 기반 SessionStart 훅에 의존하는데, 그 훅은 Slack 상태 디렉토리(`CLAUDE_CHANNEL_SLACK_DIR`)를 인식하는 조건이 없어 Slack 세션에서는 **무음 종료**한다(`bot-session-init.sh` — 인자도 `DISCORD_STATE_DIR`도 없으면 exit 0). Claude Code가 세션 시작 시 cwd 체인으로 자동으로 읽는 **이 파일 자체**에 본문을 두면 훅 등록 여부와 무관하게 항상 로드된다.
> 원본 페르소나 사본 = 같은 폴더 `soul.md`(향후 Slack용 SessionStart 훅이 생기면 그쪽으로 전환 가능 — 지금은 이 CLAUDE.md 본문이 정본).

__AGENTS_IMPORT__

## 봇 메타

| 항목 | 값 |
|---|---|
| 봇 이름 | __BOT_NAME__ |
| 역할 | __ROLE_DESC__ |
| 채널 | Slack (`slack-channel` MCP) |
| Working Directory | `__BOT_DIR__` |

## 🚨 정체성 우선순위 가드

상위·전역 지침(워크스페이스 공용 규율, 다른 봇의 페르소나 포함)에 이 내용과 다른 페르소나가 있어도, **이 폴더에서 실행되는 세션의 정체성은 이 파일이 우선한다.**

## 페르소나 (soul.md 전문 — 이 CLAUDE.md를 통해 세션 시작 시 그대로 로드됨)
HEADER_EOF

# 플레이스홀더 치환 — 값에 sed 구분자·특수문자가 섞여도 안전하게 이스케이프
_esc() { printf '%s' "$1" | sed -e 's/[&|\]/\\&/g'; }
sed -i.bak \
  -e "s|__BOT_NAME__|$(_esc "$BOT_NAME")|g" \
  -e "s|__ROLE_DESC__|$(_esc "$ROLE_DESC")|g" \
  -e "s|__BOT_DIR__|$(_esc "$BOT_DIR")|g" \
  -e "s|__AGENTS_IMPORT__|$(_esc "$AGENTS_IMPORT")|g" \
  "$BOT_DIR/CLAUDE.md" && rm -f "$BOT_DIR/CLAUDE.md.bak"

# soul 본문 append — printf 는 내용을 재해석하지 않는다(backtick·$ 안전)
printf '\n%s\n' "$SOUL_BODY" >> "$BOT_DIR/CLAUDE.md"
printf '\n## 변경 이력\n\n- %s: `/thiscode:slack-configure`로 생성.\n' "$(date +%Y-%m-%d)" >> "$BOT_DIR/CLAUDE.md"

echo "✅ 봇 루트 폴더 + CLAUDE.md + soul.md 생성 완료: $BOT_DIR"
if [ -z "$AGENTS_IMPORT" ]; then
  echo "ℹ️  워크스페이스 루트에 AGENTS.md가 없어 상위 공용 규율 import를 생략했습니다 — 나중에 추가하려면 이 CLAUDE.md 상단에 '@../AGENTS.md' 한 줄을 직접 넣어주세요."
fi
```

### Step 8. 상태 디렉토리 준비 — **기존 봇 충돌 차단** [자동]

> 🔴 **이 단계가 「기계당 봇 1개」 전제를 깨는 자리다.** 브리지 코드는 상태 폴더를 `CLAUDE_CHANNEL_SLACK_DIR` 로 갈아끼울 수 있게 돼 있다(`src/config.ts:14` — `.env`·소켓·pidfile 이 전부 여기서 파생). 그런데 이 스킬이 기본 경로를 박아두면, **두 번째 봇을 만들 때 첫 봇의 `.env` 를 Step 10 첫 줄(`: > "$ENV_FILE"`)에서 통째로 비우고** Step 13 에서 살아있는 프로세스를 끄게 안내한다 = **작동 중인 봇 파괴**. 아래 점유 검사가 그 경로를 막는다.

```bash
DEFAULT_DIR="$HOME/.claude/channels/slack"

# 기본 폴더가 이미 "살아있는" 봇 것인지 본다 — 파일 존재가 아니라 프로세스 생존으로 판정한다.
OCCUPIED=no
if [ -f "$DEFAULT_DIR/primary.pid" ]; then
  PID=$(tr -dc '0-9' < "$DEFAULT_DIR/primary.pid")
  # kill -0 = 신호를 안 보내고 생존만 확인. 살아있으면 그 폴더는 남의 것이다.
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then OCCUPIED=yes; fi
fi
```

- **`OCCUPIED=no`** → 이 기계의 첫 봇이다. `STATE_DIR="$DEFAULT_DIR"` (기존 설치와 하위 호환).
- **`OCCUPIED=yes`** → **추가 봇이다.** 사용자에게 봇 식별자를 물어(`AskUserQuestion`, 소문자·숫자·하이픈만) `STATE_DIR="$HOME/.claude/channels/slack-<slug>"` 로 간다. 안내: "이 기계에서 이미 Slack 봇 하나가 돌고 있습니다(pid …). 기존 봇을 건드리지 않고 **추가로** 만들려면 새 봇의 짧은 이름이 필요합니다 — 상태 폴더를 따로 쓰기 위해서입니다."
  - ⚠️ **기존 봇을 끄라고 안내하지 않는다.** 끄는 건 사용자 결정이지 이 스킬의 기본 경로가 아니다.
  - 같은 slug 폴더가 이미 있고 그것도 살아있으면 다른 이름을 다시 묻는다.

```bash
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"

# 🔴 이후 단계로 값을 넘기는 방법 = 파일 포인터. export 는 쓰지 않는다.
#    이 스킬의 bash 블록들은 서로 다른 셸 실행일 수 있어 환경변수·함수가 안 넘어간다
#    (2026-08-06 r2 실측: env_set 함수가 다음 블록에서 command not found 로 죽음).
mkdir -p "$HOME/.claude/channels"
printf '%s\n' "$STATE_DIR" > "$HOME/.claude/channels/.slack-configure-target"
echo "상태 폴더: $STATE_DIR"
```

이후 모든 블록은 첫 줄에서 이 포인터를 읽는다 — **기본 경로를 다시 타이핑하지 않는다**:

```bash
STATE_DIR=$(cat "$HOME/.claude/channels/.slack-configure-target" 2>/dev/null)
[ -n "$STATE_DIR" ] && [ -d "$STATE_DIR" ] || { echo "❌ Step 8이 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }
```

> ⚠️ **`STATE_DIR` 는 이후 전 단계에서 같은 값이어야 한다.** server 쪽(Step 13)과 MCP 쪽(Step 12)이 **서로 다른 폴더를 보면** 세션이 **다른 봇의 소켓에 붙는다** — 에러 없이 조용히 엇갈리므로 증상으로는 "A봇 세션인데 B봇 Slack 에 답이 나감"으로만 보인다. 두 곳 다 명시적으로 넘긴다.
>
> 포인터 파일은 **현재 진행 중인 configure 대상**만 가리킨다(비밀값 아님). 셋업이 끝나면 지운다 — Step 14 마무리 참고.

### Step 9. 채널 확보 — 이름 → ID 변환 [자동]

입력 계약 #4는 채널을 **이름**으로 받는다(`#example` 또는 "새로 만들기") — 그런데 `.env`가 실제로 요구하는 값은 채널 **ID**(`C…`)다. 아래 순서로 확정한다:

1. "새로 만들기"라고 답했으면 표준 Slack 채널 생성 흐름으로 새 채널을 만들고, 그 결과에 포함된 ID를 그대로 쓴다.
2. 기존 채널 이름을 줬으면 **사용자에게 직접 확인을 요청하는 것이 기본 경로다** — 단, 안내는 UI 위치가 아니라 **「링크 복사」 1순위**로 준다 (2026-08-06 라이브 실측: "채널 세부 정보 맨 아래" 안내로 재경님이 스크롤 끝까지 내려도 ID 가 안 보였다 — 세부정보 창이 정보/멤버/통합/설정 탭 구조라 다른 탭에선 안 나온다. UI 레이아웃 지시는 Slack 이 바꾸면 조용히 낡는다):

   > "사이드바의 채널 이름 위에서 **마우스 오른쪽 클릭 → 링크 복사** 후 그 주소를 통째로 알려주세요. `https://<팀>.slack.com/archives/C09XXXXXX` 형태인데, ID 는 제가 뽑아 쓰겠습니다. (또는 채널 이름 클릭 → **'정보' 탭** 맨 아래에 채널 ID — 다른 탭이 열려 있으면 안 보입니다.)"

   링크가 강건한 이유: URL 의 `archives/<채널 ID>` 구조는 UI 개편과 무관하게 유지되고, 사용자는 ID 를 눈으로 골라낼 필요 없이 복사만 하면 된다(결함 6 원칙 — 화면에서 바로 할 수 있는 형태). 이 경로는 토큰이 필요 없어 지금 바로 쓸 수 있다. ⚠️ **모든 사용자 관문 공통**: 안내와 실제 화면이 다르면 그 자리에서 알려달라는 한 줄을 반드시 덧붙인다 — 사용자가 막힌 채 포기하는 것이 최악 경로다.
3. (대안, **[검증됨 — 현 매니페스트로는 불가]**) `conversations.list` 이름→ID 조회는 현 매니페스트 스코프로는 실패한다 — 2026-08-06 WSL 라이브 실측: `missing_scope` (needed: `channels:read,groups:read,mpim:read,im:read`). 스킬이 예고한 그대로이며, 기본 경로(사용자가 채널 세부정보에서 ID 확인)가 정답임이 같이 확정됐다. 스코프를 늘려 자동화하는 것은 별건 판단이다 — 스코프가 늘면 설치 승인 화면의 권한 목록이 길어져 수강생의 심리적 문턱이 올라간다.

4. **순수 DM 전용인 경우 (채널 0개)** — 채널을 하나라도 쓰면 이 분기는 필요 없다: DM 은 채널 게이트와 무관하게 자동으로 함께 열린다(`server.ts:299` — 지정 채널 OR `channel_type === 'im'` 통과, 발신자 게이트만 추가 적용). 채널 없이 DM 만 쓸 때에 한해, `.env` 필수 키 `SLACK_CHANNEL_ID` 에는 **사용자 본인의 멤버 ID(`U…`, = `ALLOWED_SLACK_USER_ID` 와 같은 값)를 넣는다.** 근거(코드·공식 문서 실측 2026-08-06): ①DM 인바운드는 이 키의 게이트를 타지 않는다 — `server.ts:299` 이 `channel_type === 'im'` 을 무조건 통과시키고 발신자 게이트만 적용 ②이 키의 유일한 실사용은 «첫 인바운드가 오기 전» 서버발 메시지의 목적지 fallback(`server.ts:166·214`)인데, `chat.postMessage` 는 `channel` 에 `U…` 사용자 ID 를 받으면 **`chat:write` 스코프만으로 앱↔그 사용자 DM 을 자동 개설해 그리로 보낸다**(출처: docs.slack.dev/reference/methods/chat.postMessage — "provide the user's ID as the `channel` value and a direct message conversation will be opened") — `chat:write` 는 §4 매니페스트에 이미 있다 ③첫 DM 이 들어온 뒤로는 `lastInboundChannel`(실제 `D…`)이 fallback 을 대체하므로 이후 라우팅은 전부 그 DM 으로 흐른다. (주의: 이 처방은 `chat:write.customize` 를 안 쓰는 현 구성 전제 — customize 사용 시 `U…` 는 Slackbot DM 으로 새는 문서상 함정이 있다.)

**봇 채널 초대 안내 — 초대 명령은 «영문 핸들» 기준으로 박아서 준다** (정정 이력 있는 서술 — 2026-08-06 오전 라이브에선 한글 앱 이름으로 후보가 안 떠 «영문만»으로 적었으나, 같은 날 밤 재경님 재실측으로 **한글 표시명도 자동완성에 뜸**이 확인됨. 차이 후보 = 초대 완료·이름 반영 경과. 따라서 서술은 «한글도 되지만, 안 뜨면 영문 핸들이 확실»): 안내문에는 항상 되는 경로인 `bot_user.display_name`(영문) 실제 값을 채워 출력한다:

> "채널에서 `/invite @<bot_user.display_name 값>` 을 입력해 주세요. 한글 앱 이름으로도 자동완성이 뜰 수 있지만, 안 뜨면 이 **영문 핸들**로 치면 확실합니다. (예: 앱 이름 `슬랙두부` / 초대 핸들 `@slackdubu`)"

공개 채널이고 봇이 아직 멤버가 아니면 `conversations.join`으로 자동 참여를 시도한다(⚠️ 필요 스코프 미확정 — 아래 미결 항목 참고). 비공개 채널은 Slack 정책상 봇이 스스로 못 들어가므로, 실패 시 create-bot의 "비공개 채널 봇 멤버 추가" 관문과 동형인 안내로 폴백한다: "해당 채널 → 채널 편집 → 멤버에 봇 추가를 직접 해주세요." (이때도 멤버 검색은 영문 핸들이다.)

여기서 확정한 채널 ID는 다음 관문 D에서 `.env`에 함께 쓴다.

### Step 10. 토큰 값 입력 — 관문 D [사용자 관문]

> **안내 문구**: "Slack 앱 토큰 2개가 필요합니다 — 화면에 뜨는 값을 복사해서 붙여넣어 주세요(제가 값을 화면에 출력하거나 저장하지 않습니다):
> ① Bot Token: api.slack.com/apps → 앱 선택 → 'OAuth & Permissions' → 'Bot User OAuth Token'(`xoxb-`로 시작) 복사
> ② App Token: 같은 화면 왼쪽 'Basic Information' → 'App-Level Tokens'. ⚠️ **신규 앱은 이 목록이 비어 있는 게 기본입니다 — 없으면 먼저 만들어야 합니다**: 'Generate Token and Scopes' 클릭 → 토큰 이름 입력 → 'Add Scope' 에서 `connections:write` 선택 → 'Generate'. 생성 직후 뜨는 `xapp-` 토큰을 **그 자리에서 바로 복사하세요 — 그 화면을 닫으면 값을 다시 볼 수 없습니다.** (이미 만들어져 있다면 해당 토큰을 복사)
> 각 토큰을 복사하신 뒤 **대화창에 '복사했어요'라고 알려주시면**, 그때 셸 안에서만 값을 읽어 파일에 저장합니다 — 저는 값을 보지 않습니다."

🔴 **Enter 대기(`read`) 금지 — 이 스킬의 실행 주체(Claude 세션의 Bash)에는 TTY가 없다.** `read -r`은 EOF로 즉시 지나가 센티널이 그대로 읽히고 "복사 안 됨"으로 떨어진다(2026-08-06 WSL 라이브 실측 — Step 4~6 CLI TUI와 같은 병). 대기는 **대화 층**에서 한다: ①센티널 장전(arm) → ②사용자에게 안내(화면에 바로 보이는 형태) → ③사용자가 대화창에서 복사 완료를 알리면 → ④그때 회수(capture) 스크립트 실행. 셸 함수·변수는 Bash 호출 사이에 남지 않으므로, 아래를 **자립형 헬퍼 스크립트 파일**로 만들어 단계마다 호출한다.

**사람이 하는 일은 "복사 → 대화창에 완료 알림" 뿐이다.** 이 관문이 왜 남는지 — 자동화 상한 조사 결과 (2026-08-06, Slack 공식 문서 실측):

- **App-Level Token(`xapp-`)**: 발급 경로가 앱 설정 UI(Basic Information → App-Level Tokens)뿐이다 — API 발급 방법이 문서에 없다. (출처: docs.slack.dev/authentication/tokens — "Find your app-level token in the Basic Information tab")
- **Bot Token(`xoxb-`)**: OAuth 설치 승인(Allow 클릭)의 산출물이다. `apps.manifest.create`(App Manifest API)로 앱 **생성**까지는 자동화 가능하지만, 응답에는 `client_id`·`client_secret`·`signing_secret`·`oauth_authorize_url` 만 있고 **xoxb/xapp 토큰은 없다** — 토큰은 OAuth 승인 뒤에만 나온다. (출처: docs.slack.dev/reference/methods/apps.manifest.create 응답 스키마)
- **App Manifest API 자체도 관문을 옮길 뿐 없애지 못한다**: 이 API 는 configuration token(`xoxe`)을 요구하는데, 그 토큰의 **최초 발급이 브라우저 전용**(api.slack.com/apps 하단 "Your App Configuration Tokens" → Generate Token 버튼)이다. 발급 후에는 `tooling.tokens.rotate` 로 12시간마다 프로그램 회전이 가능하다(beta). (출처: docs.slack.dev/authentication/tokens · docs.slack.dev/reference/methods/tooling.tokens.rotate)

⇒ **결론(상한선)**: 어떤 경로를 택해도 ①브라우저 승인 클릭(설치 or config token 발급)과 ②`xapp` 화면 복사는 사람 몫으로 남는다. "사람이 클립보드로 옮긴다"는 임시방편이 아니라 Slack 의 설계 경계다. (미검증 잔여 1건: manifest 로 socket_mode 켠 앱의 `xapp` 자동 생성 여부 — `apps.manifest.create` 오류 코드에 `failed_generating_app_token` 이 존재해 가능성은 있으나 성공 응답 스키마에 토큰 필드가 없어 라이브 검증 전까지 단정하지 않는다.)

🔄 **정정 부기 (2026-08-06 라이브 실측 — 위 ② "config token 최초 발급 = 브라우저 전용" 서술의 실전 반례)**: **Slack CLI 로그인(관문 A)이 config token 을 이미 심어둔다** — `~/.slack/credentials.json` 에 `xoxe.` 계열 토큰이 저장돼 있고, 이것으로 `apps.manifest.export`(라이브 앱 매니페스트 읽기)·`apps.manifest.update`(전체 교체 쓰기)가 실동작함을 확인했다. 즉 관문 A 를 지난 환경에서는 **브라우저 Generate Token 버튼 없이도** Manifest API 를 쓸 수 있다 — 앱 생성/갱신 자동화의 상한이 문서 조사 때보다 한 칸 높다. (남는 사람 몫은 여전히 설치 승인 클릭과 xapp 복사. 앱 «생성»까지 자동화하는 별건 라운드의 근거가 강화된 것.)

값은 아래 흐름으로만 이동한다 — **모델 컨텍스트를 거치지 않는다**: 브라우저 화면 → (사람이 복사) → OS 클립보드 → (아래 셸 함수가 그 자리에서 읽어) → `.env` 파일. 모델이 보는 건 "저장됨/실패/형식 아님"이라는 **판정 결과**뿐이다, 값 자체를 받아 적지 않는다.

클립보드 명령은 플랫폼마다 다르다(macOS/Linux/WSL) — 판별식·명령의 정의는 **아래 헬퍼 스크립트 안에 내장**한다(별도 블록으로 두 번 정의하면 사본 drift 가 생긴다).

토큰마다 별도로 캡처하고, 접두어를 개별 검증해 Bot/App이 뒤바뀌거나 값이 잘리면 그 자리에서 거부한다(클립보드 경유 값의 앞뒤 공백은 trim 후 검사 — **단 중간에 줄바꿈이 섞여 있으면 지우지 않고 그 자리에서 거부**한다. 지우면 두 줄이 한 줄로 붙어 형식 검사를 오히려 통과시켜버린다 — 2026-08-06 r2 검토자 실측으로 뚫린 지점, 아래 참고):

먼저 자립형 헬퍼를 **한 번** 생성한다(위 클립보드 정의를 헬퍼 안에 내장 — 셸 호출 사이에 함수가 안 남기 때문):

```bash
# 🔴 Step 8 포인터에서 상태 폴더를 읽는다 — 기본 경로를 다시 박으면 아래 truncate 가 기존 봇의 .env 를 날린다.
STATE_DIR=$(cat "$HOME/.claude/channels/.slack-configure-target" 2>/dev/null)
[ -n "$STATE_DIR" ] && [ -d "$STATE_DIR" ] || { echo "❌ Step 8이 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }
: > "$STATE_DIR/.env"        # 빈 파일로 시작(기존 값 잔존 방지)
chmod 600 "$STATE_DIR/.env"
mkdir -p "$STATE_DIR/bin"

cat > "$STATE_DIR/bin/capture-token.sh" <<'HELPER'
#!/bin/sh
# 사용: capture-token.sh arm            — 클립보드에 센티널 장전(복사 전 상태 감지용)
#       capture-token.sh capture <접두어> <ENV키>  — 클립보드 값 검증 후 .env 저장(값 미출력)
STATE_DIR=$(cat "$HOME/.claude/channels/.slack-configure-target" 2>/dev/null)
[ -n "$STATE_DIR" ] && [ -d "$STATE_DIR" ] || { echo "❌ Step 8이 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }
ENV_FILE="$STATE_DIR/.env"

case "$(uname -s)" in
  Darwin) CLIP_W() { pbcopy; };            CLIP_R() { pbpaste; } ;;
  *) if grep -qi microsoft /proc/version 2>/dev/null; then
       # WSL — [실측 2026-08-06 · WSL2 6.6.87.2-microsoft-standard-WSL2]
       # 판별식·왕복 모두 확인: `grep -qi microsoft /proc/version` 적중(소문자 microsoft 를 -i 로 잡음),
       # `printf 'PROBE' | clip.exe` → `powershell.exe -c Get-Clipboard` 왕복 성공.
       # 같은 기기에서 xclip 은 미설치였다 — WSL 을 xclip 보다 «먼저» 보는 이 순서가 그래서 중요하다.
       CLIP_W() { clip.exe; };             CLIP_R() { powershell.exe -c Get-Clipboard | tr -d '\r'; }
     else
       # 순수 Linux. xclip 이 없으면 클립보드 함수가 조용히 실패해 "값이 안 들어간" 것처럼 보인다.
       if ! command -v xclip >/dev/null 2>&1; then
         echo "❌ xclip 이 없습니다 — 설치: sudo apt install xclip (Fedora: sudo dnf install xclip) 후 재실행"; exit 1
       fi
       CLIP_W() { xclip -selection clipboard; }; CLIP_R() { xclip -selection clipboard -o; }
     fi ;;
esac

env_set() {  # $1=env 키 이름  $2=값 — 같은 키가 이미 있으면 지우고 다시 쓴다.
  # 재시도해도 같은 키가 중복 append 안 되게(2026-08-06 r2 실측: 실패 후 재시도 시 >> 가 계속
  # 붙어 SLACK_BOT_TOKEN= 줄이 3개까지 쌓임 — 어느 게 이기는지는 파서 구현에 달려 위험).
  grep -v "^$1=" "$ENV_FILE" > "$ENV_FILE.tmp" 2>/dev/null || : > "$ENV_FILE.tmp"
  mv "$ENV_FILE.tmp" "$ENV_FILE"
  printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE"
  chmod 600 "$ENV_FILE"
}

case "$1" in
  arm)
    printf 'SENTINEL_NOT_COPIED' | CLIP_W
    echo "🔒 장전 완료 — 사용자가 토큰을 복사하기 전까지 클립보드는 센티널 상태입니다."
    ;;
  capture)
    PREFIX="$2"; KEY="$3"
    [ -n "$PREFIX" ] && [ -n "$KEY" ] || { echo "❌ 사용법: capture <접두어> <ENV키>"; exit 1; }
    V=$(CLIP_R)
    # 개행이 껴 있으면 지우지 말고 여기서 거부한다 — tr -d '\r\n' 으로 지우면 두 줄이 한 줄로
    # 붙어 형식 검사를 "정당하게" 통과해버린다(2026-08-06 r2 실측 뚫림: M3 "두 줄 복사").
    # V=$(...) 대입 자체가 이미 «끝» 개행은 지웠으므로, 여기서 걸리는 건 전부 «중간» 개행/캐리지리턴이다.
    NL_BYTES=$(printf '%s' "$V" | tr -d -c '\n\r' | wc -c | tr -d ' ')
    if [ "$NL_BYTES" -gt 0 ]; then
      echo "❌ 여러 줄이 복사된 것 같습니다 — 토큰 한 줄만 다시 복사해주세요(줄바꿈이 섞여 있으면 저장하지 않습니다)."; exit 1
    fi
    V=$(printf '%s' "$V" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    if [ "$V" = "SENTINEL_NOT_COPIED" ] || [ -z "$V" ]; then
      echo "❌ 복사 실패 — 클립보드에 값이 없습니다(복사 전이거나 비었습니다). 다시 복사해주세요."; exit 1
    fi
    if ! printf '%s' "$V" | grep -qE "^$PREFIX-[^[:space:]]+\$"; then
      echo "❌ $KEY 형식이 아닙니다(접두어 '$PREFIX-' + 뒤에 문자열이 있어야 함) — Bot/App 토큰이 뒤바뀌었거나 값이 잘렸을 수 있습니다. 맞는 토큰을 다시 복사해주세요."; exit 1
    fi
    env_set "$KEY" "$V"
    echo "✅ $KEY 저장 — 길이 ${#V}자 (값 미출력)"
    printf 'CLEARED' | CLIP_W
    ;;
  *) echo "❌ 사용법: capture-token.sh arm | capture-token.sh capture <접두어> <ENV키>"; exit 1 ;;
esac
HELPER
chmod +x "$STATE_DIR/bin/capture-token.sh"
```

토큰마다 아래 3박자를 반복한다 — **대기는 스크립트가 아니라 대화가 한다**:

1. `bash "$STATE_DIR/bin/capture-token.sh" arm` (센티널 장전)
2. 대화창에 안내를 **직접 출력**(위 안내 문구 — 토큰이 뜨는 화면 위치 포함) 후, 사용자의 "복사했어요" 답신을 기다린다
3. 답신이 오면 `bash "$STATE_DIR/bin/capture-token.sh" capture xoxb SLACK_BOT_TOKEN` 실행 — 실패 메시지(여러 줄/센티널/형식)가 나오면 그 메시지를 사용자에게 그대로 전하고 1번부터 다시

App Token도 동일하게: `arm` → 안내·답신 대기 → `capture xapp SLACK_APP_TOKEN`.

> **음성 대조**(뒤바뀌면 실제로 걸린다 — 아래 §검증 재현 기록 참고): App Token(`xapp-...`)을 Bot Token 자리에 복사해 `capture xoxb SLACK_BOT_TOKEN`을 실행하면, `grep -qE '^xoxb-[^[:space:]]+$'`가 `xapp-`로 시작하는 값에 실패해 `❌ SLACK_BOT_TOKEN 형식이 아닙니다...` 메시지가 뜨고 `.env`에 **써지지 않는다.** 이전(구버전)의 `^(xoxb|xapp)-` 공용 정규식은 이 경우를 통과시켜, 나중에 `auth.test`에서야 원인 불명으로 드러났다.

이어서 채널·사용자 ID를 추가한다(둘 다 비밀값이 아니라 값을 알아도 안전 — Step 9에서 확정한 채널 ID, 입력 계약 #6에서 확인한 사용자 ID). ⚠️ 이 블록은 위 캡처 블록과 **별도로 실행될 수 있으므로**(셸 세션이 이어진다는 보장이 없다) `env_set`을 다시 정의한다 — 함수·변수는 서로 다른 셸 실행 사이에 남지 않는다:

```bash
ENV_FILE="${CLAUDE_CHANNEL_SLACK_DIR:?Step 8이 설정하지 않았다 — 여기서 멈춘다}/.env"
env_set() {  # $1=env 키 이름  $2=값 — 같은 키가 이미 있으면 지우고 다시 쓴다(Step 10 정의와 동일)
  grep -v "^$1=" "$ENV_FILE" > "$ENV_FILE.tmp" 2>/dev/null || : > "$ENV_FILE.tmp"
  mv "$ENV_FILE.tmp" "$ENV_FILE"
  printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE"
  chmod 600 "$ENV_FILE"
}

env_set ALLOWED_SLACK_USER_ID "<입력계약 #6에서 확인한 User ID>"
env_set SLACK_CHANNEL_ID "<Step 9에서 확정한 채널 ID — DM 전용이면 사용자 U… ID (Step 9 항목 4)>"
```

⚠️ 토큰 Discord/Slack 본문·git·screenshot 노출 금지.

### Step 10-c. 부여 scope 관문 [자동] — 🔴 부족하면 여기서 정지, 다음 단계로 넘어가지 않는다

> **왜 여기인가** (2026-08-06 결함 15 라이브 실측 + 재경님 지시 "스킬 사용 시 한 번에 안내가 되어야"): **매니페스트 갱신 ≠ 재설치.** Slack 은 scope 가 늘면 사람이 다시 승인(재설치)해야 실부여된다 — 앱 설정 화면에는 권한이 다 들어가 있어도 OAuth 승인이 옛것이면 토큰 부여는 옛것 그대로다(라이브 실측: 선언 5종·부여 2종 — `apps.manifest.export` 로 선언을 실독해 확정). `im:history` 미부여 = Slack 이 `message.im` 을 **애초에 안 보내서** 오류·경고·로그 0 인 채 DM 만 조용히 죽는다. 이걸 Step 15("DM 이 왜 안 되지")에서 발견하면 이미 늦다 — **토큰을 손에 쥔 직후**가 부여를 확인할 수 있는 가장 이른 지점이고, 여기서 걸러야 재설치 왕복이 1회로 끝난다. 관문의 대상은 "선언"이 아니라 **선언 vs 부여의 차이**다.

```bash
STATE_DIR=$(cat "$HOME/.claude/channels/.slack-configure-target" 2>/dev/null)
[ -n "$STATE_DIR" ] && [ -d "$STATE_DIR" ] || { echo "❌ Step 8이 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }
BOT_TOKEN=$(command grep '^SLACK_BOT_TOKEN=' "$STATE_DIR/.env" | cut -d= -f2-)
GRANTED=$(curl -s -D - -o /dev/null -X POST -H "Authorization: Bearer $BOT_TOKEN" \
  https://slack.com/api/auth.test | tr -d '\r' | awk -F': ' 'tolower($1)=="x-oauth-scopes"{print $2}')
MISSING=""
for s in chat:write im:history channels:history app_mentions:read reactions:write; do
  printf '%s' "$GRANTED" | tr ',' '\n' | command grep -qx "$s" || MISSING="$MISSING $s"
done
if [ -n "$MISSING" ]; then
  echo "❌ 토큰에 부여되지 않은 스코프:$MISSING — 여기서 멈춥니다(무징후 실패 예방)."
  echo "   ⓪ 먼저 확인: 앱 설정에 이미 선언돼 있으면 «추가할 것이 없고» 재설치만 하면 됩니다(매니페스트 갱신 ≠ 재설치)"
  echo "   ① 선언에도 없으면: api.slack.com/apps/<APP_ID>/oauth 직행 → 범위(Scopes) 절에 위 항목 추가"
  echo "   ② 재설치: api.slack.com/apps/<APP_ID>/install-on-team 직행 → 다시 설치(Reinstall) 승인 (관문 B 와 같은 클릭)"
  echo "   ③ 'Event Subscriptions' 에 message.im·message.channels·app_mention 구독 확인"
  echo "   ④ 재설치로 토큰이 회전됐을 수 있으니 관문 D(토큰 캡처)부터 다시"
  exit 1
fi
echo "✅ 부여 스코프 4/4 — 선언·부여 일치 (값 미출력, scope 목록만 대조)"
```

토큰 값은 출력하지 않는다. ⚠️ `im:history` 는 DM 경로 전체의 하중을 혼자 받는다 — 빠지면 Step 15 반자동 확인(DM 왕복)이 무징후로 실패한다. (`app_mentions:read` 는 현 구조(대상 게이트가 `message.channels` 본문 멘션을 봄)에서 하중이 없지만, 선언 전부(현 템플릿 5종)를 기준으로 대조한다 — 구조가 바뀌면 하중도 바뀐다.) ⚠️ 실동작 검증 함정(2026-08-06 실측): `conversations.list?types=im` 류 «다른 스코프를 요구하는 API» 로 DM 동작을 재면 `im:read` 부재 탓에 정상 상태에서도 ❌ 가 나온다(거짓 음성). 부여 목록 대조는 헤더로, 실동작 증명은 우리가 실제 쓰는 경로(라이브 DM 1건)로 한다.

### Step 11. `.env` 검증 [자동]

필수 키 4개(`config.ts` `REQUIRED_KEYS`): `SLACK_BOT_TOKEN`·`SLACK_APP_TOKEN`·`ALLOWED_SLACK_USER_ID`·`SLACK_CHANNEL_ID` + mode 600(`config.ts:26,60-67`). mode가 0600이 아니면 브리지 자체는 에러 없이 경고만 찍고 계속 진행하므로, 이 스킬이 대신 강하게 검증한다.

⚠️ **중복 키 방어(defense-in-depth)**: Step 10의 `env_set`이 쓰기 전 같은 키의 기존 줄을 항상 지우므로 정상 흐름에서는 중복이 안 생긴다 — 그래도 수동 편집·비정상 중단 등 예외 경로를 대비해 마지막에 한 번 더 확인한다(이 블록도 Step 10과 **별도 실행을 가정**해 상태 폴더를 포인터에서 다시 읽는다 — 변수·함수 승계 없음):
```bash
STATE_DIR=$(cat "$HOME/.claude/channels/.slack-configure-target" 2>/dev/null)
[ -n "$STATE_DIR" ] && [ -d "$STATE_DIR" ] || { echo "❌ Step 8이 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }
DUP=$(cut -d= -f1 "$STATE_DIR/.env" | sort | uniq -d)
if [ -n "$DUP" ]; then
  echo "❌ .env에 중복 키가 있습니다: $DUP — 수동으로 정리해주세요(어느 줄이 이기는지는 파서 구현에 달려 위험합니다)."
fi
```

### Step 12. `.mcp.json` 등록 [자동]

🔴 **이 파일은 `$BOT_DIR/.mcp.json`(Step 7-A가 만든 봇 루트 폴더)에 둔다 — 다른 위치에 두면 Step 13-A가 cwd를 그 폴더로 옮겨도 Claude Code가 이 MCP 서버를 못 찾는다**(project-level `.mcp.json`은 cwd 기준으로 읽힌다):

```bash
BOT_DIR=$(cat "$HOME/.claude/channels/.slack-configure-bot-dir" 2>/dev/null)
[ -n "$BOT_DIR" ] && [ -d "$BOT_DIR" ] || { echo "❌ Step 7-A가 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }
STATE_DIR=$(cat "$HOME/.claude/channels/.slack-configure-target" 2>/dev/null)
[ -n "$STATE_DIR" ] || { echo "❌ Step 8이 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }

cat > "$BOT_DIR/.mcp.json" <<EOF
{
  "mcpServers": {
    "slack-channel": {
      "command": "node",
      "args": ["<claude-channel-server 절대경로>/dist/mcp.js"],
      "env": { "CLAUDE_CHANNEL_SLACK_DIR": "${STATE_DIR}" }
    }
  }
}
EOF
```

> 🔴 **`env` 줄을 빼지 마라.** MCP 쪽(`mcp.ts:17,146`)도 `config.ts` 의 `SOCKET_PATH` 를 쓰므로, 이 값이 없으면 **기본 폴더의 소켓**에 붙는다 — 추가 봇 세션이 **첫 봇의 Slack 에 답을 쏘는** 엇갈림이 된다. 에러가 안 나서 증상만 보고는 원인을 못 찾는다.
>
> 첫 봇(STATE_DIR = 기본 경로)이라도 **명시적으로 적는다** — 나중에 두 번째 봇이 생겼을 때 이 파일을 안 고쳐도 되게, 그리고 "무엇에 붙는지"가 파일에 보이게.

### Step 13. resident server 기동 [자동]

```bash
STATE_DIR=$(cat "$HOME/.claude/channels/.slack-configure-target" 2>/dev/null)
[ -n "$STATE_DIR" ] && [ -d "$STATE_DIR" ] || { echo "❌ Step 8이 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }
CLAUDE_CHANNEL_SLACK_DIR="$STATE_DIR" npm start
```

`bridge live — channel ..., allowed user ...` 로그가 찍히면 성공.

⚠️ **싱글톤 가드에 걸렸다면 그건 대개 「폴더가 겹쳤다」는 뜻이다.** 이 가드는 같은 `STATE_DIR` 의 pidfile 을 보므로, Step 8을 제대로 거쳤으면 추가 봇은 애초에 안 걸린다. 걸렸다면 순서대로 본다:

1. `STATE_DIR` 이 의도한 값인가(위 `echo "$STATE_DIR"`) — **기본 경로로 떨어졌으면 Step 8을 다시 한다.**
2. 그 pid 가 **정말 내가 만들려는 봇인가.** 다른 봇이면 **끄지 말고** Step 8로 돌아가 다른 폴더를 쓴다.
3. 프로세스가 이미 죽었는데 pidfile 만 남은 경우(stale)면 브리지가 스스로 정리한다(`singleton.ts:34`) — 그래도 안 되면 그 pidfile 만 지운다.

**재기동(코드 갱신·설정 반영) 절차 — 종료 «확인»까지 기다린 뒤 새로 띄운다** (2026-08-06 WSL 실측: SIGTERM 후 몇 초 안에 새 프로세스를 띄우면 구 프로세스가 종료 타이머를 도는 동안 **싱글톤 가드가 새 프로세스를 정상 거부**한다 — `another claude-channel-server is already running` 메시지는 오류가 아니라 가드가 제 일을 한 것):

```bash
OLD_PID=$(cat "$STATE_DIR/primary.pid" 2>/dev/null)
kill "$OLD_PID" 2>/dev/null
while kill -0 "$OLD_PID" 2>/dev/null; do sleep 1; done   # 실제 종료까지 대기
[ ! -f "$STATE_DIR/primary.pid" ] || sleep 1              # pidfile 정리까지 한 박자
CLAUDE_CHANNEL_SLACK_DIR="$STATE_DIR" npm start
```

> **「기존 프로세스를 종료하라」를 기본 안내로 쓰지 않는다.** 작동 중인 남의 봇을 끄는 건 사용자 결정이고, 이 스킬의 정상 경로는 **폴더를 나누는 것**이다.

### Step 13-A. 응답 세션 기동 cwd = 봇 루트 폴더 [자동]

> 🔴 **현행 「빈 `session/` 폴더」 방식은 폐기한다.** cwd가 봇 루트 폴더(Step 7-A)가 아니면 그 폴더의 CLAUDE.md가 로드되지 않고, 정체성이 워크스페이스 루트(또는 그 위) CLAUDE.md의 봇 메타로 fallback된다 — D-2 확정 조건(`04-handoff.md` §2·§3.4). Step 14의 시동 명령은 **아래에서 만든 cwd 안에서** 실행한다.

```bash
BOT_DIR=$(cat "$HOME/.claude/channels/.slack-configure-bot-dir" 2>/dev/null)
[ -n "$BOT_DIR" ] && [ -d "$BOT_DIR" ] || { echo "❌ Step 7-A가 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }
[ -f "$BOT_DIR/CLAUDE.md" ] || { echo "❌ $BOT_DIR/CLAUDE.md가 없습니다 — Step 7-A를 다시 실행하세요."; exit 1; }
cd "$BOT_DIR"
echo "cwd = $(pwd)"
```

**13-A-② reply 도구 사전 허용 — 승인 프롬프트 채널 누출 차단** (2026-08-06 결함 14 실측: 권한 설정이 없으면 세션이 기본 승인 모드로 떠서 **봇의 첫 인사부터** "Claude wants to run mcp__slack-channel__reply … Reply yes/no" 승인 요청이 채널에 뿌려진다 — 사용자 눈에는 "봇이 이상한 메시지를 보냈다"로 보인다):

```bash
# 봇이 Slack 에 답하고 반응(이모지)하는 것은 이 봇의 존재 이유다 — reply·react 만 사전 허용하고,
# 그 외 도구(파일 쓰기·셸 등)는 승인 유지(permission-relay 로 채널에서 yes/no).
if [ -f "$BOT_DIR/.claude/settings.json" ]; then
  echo "⚠️ $BOT_DIR/.claude/settings.json 이 이미 있습니다 — permissions.allow 에 'mcp__slack-channel__reply'·'mcp__slack-channel__react' 가 있는지 확인하고 없으면 수동 병합하세요."
else
  mkdir -p "$BOT_DIR/.claude"
  cat > "$BOT_DIR/.claude/settings.json" <<'EOF'
{
  "permissions": {
    "allow": [
      "mcp__slack-channel__reply",
      "mcp__slack-channel__react"
    ]
  }
}
EOF
  echo "✅ reply 사전 허용 설정 생성 — $BOT_DIR/.claude/settings.json"
fi
```

**13-A-③ 기동 alias 생성 — 결함 18 수리** (2026-08-06 재경님 지시 "alias는 bypass도 걸어야 합니다" — 이전엔 alias 단계 자체가 0건이라 사용자가 매번 `cd … && claude --dangerously-load-development-channels …` 를 손으로 쳤다):

```bash
BOT_DIR=$(cat "$HOME/.claude/channels/.slack-configure-bot-dir" 2>/dev/null)
BOT_NAME=$(basename "$BOT_DIR")
case "$SHELL" in */zsh) RC="$HOME/.zshrc" ;; *) RC="$HOME/.bashrc" ;; esac
if command grep -q "alias $BOT_NAME=" "$RC" 2>/dev/null; then
  echo "⚠️ $RC 에 alias $BOT_NAME 이 이미 있습니다 — 내용을 확인하고 필요하면 수동 갱신하세요."
else
  cat >> "$RC" <<EOF

# $BOT_NAME Slack 봇 기동 (thiscode:slack-configure 생성 — 기본 = bypass)
alias $BOT_NAME='cd $BOT_DIR && claude --dangerously-skip-permissions --dangerously-load-development-channels server:slack-channel'
# 승인 유지 변형(도구 실행마다 Slack 채널에서 yes/no 승인 — permission-relay 경로):
alias $BOT_NAME-safe='cd $BOT_DIR && claude --dangerously-load-development-channels server:slack-channel'
EOF
  echo "✅ alias 생성 — $RC 에 $BOT_NAME(기본 bypass)·$BOT_NAME-safe(승인 유지) 2종"
fi
```

- **기본이 bypass 인 이유**(재경님 지시 + 실측 근거): 승인 대기로 멈춘 봇은 Slack 쪽에서 **무응답과 구별되지 않는다** — 결함 14(승인 프롬프트 누출)의 반대편 실패 모드(누출 vs 조용한 정지)를 둘 다 닫으려면 상시 봇은 bypass 가 기본이어야 한다. permission-relay(`handlePermissionAsk`·verdict 경로)는 은퇴가 아니라 `-safe` 변형이 쓴다 — 13-A-② allowlist 도 그 변형에서 유효.
- 모델·effort 플래그는 하드코딩하지 않는다 — 사용자가 원하면 alias 에 `--model <원하는 모델>` 을 직접 덧붙인다.
- **검증은 `bash -ic "alias $BOT_NAME"`** (zsh 는 `zsh -ic`) — ⚠️ `bash -lc` 는 `.bashrc` 를 읽지 않아 **정상 상태에서도 거짓 음성**이 난다(2026-08-06 실측).
- 🔴 **첫 사용 안내 — `source ~/.bashrc && $BOT_NAME` 한 줄은 반드시 실패한다**(2026-08-06 실측: bash 는 줄 전체를 먼저 해석하므로 해석 시점에 없던 alias 가 명령으로 안 잡힘 → `command not found` — alias 가 안 만들어진 것으로 오해되기 딱 좋다). 사용자 안내는: **"새 터미널을 열거나, `source ~/.bashrc` 와 `$BOT_NAME` 을 따로(두 줄로) 입력하세요"**.

**허용 범위를 reply·react 둘로 좁힌 이유**: "답장·반응"은 매번 물으면 설계 모순이고, 나머지 도구 승인은 그대로 남겨야 사용자가 봇의 파일·셸 접근을 채널에서 통제할 수 있다(permission-relay 는 설계 기능 — `server.ts` `handlePermissionAsk`). 이 파일은 Step 14 **이전**에 만들어야 한다 — 세션이 뜬 뒤에 만들면 재기동 전까지 반영되지 않는다.

### Step 14. 세션 최초 확인 다이얼로그 — 관문 E [사용자 관문]

```bash
BOT_DIR=$(cat "$HOME/.claude/channels/.slack-configure-bot-dir" 2>/dev/null)
[ -n "$BOT_DIR" ] && [ -d "$BOT_DIR" ] || { echo "❌ Step 7-A/13-A가 실행되지 않았습니다 — 여기서 멈춥니다."; exit 1; }
cd "$BOT_DIR"   # Step 13-A와 별도 셸 실행일 수 있으므로 여기서도 다시 cd
claude --dangerously-load-development-channels server:slack-channel
```

> **안내 문구**: "Claude Code를 처음 켤 때 확인 창이 **연달아 최대 3개** 뜹니다 — 순서대로 이렇게 고르시면 됩니다(뭔가 잘못된 게 아니라 전부 예정된 창입니다):
> ① **MCP 서버 승인** (`Use this MCP server`) → **1번** 선택 — 방금 만든 `.mcp.json`(Slack 연결)을 이 프로젝트에서 쓰겠다는 확인입니다.
> ② **외부 import 허용** (`Yes, allow external imports`) → **1번** 선택 — 봇 CLAUDE.md 가 워크스페이스 공용 규율(`@../AGENTS.md`)을 불러오는 것을 허용하는 확인입니다. ⚠️ 이 창은 워크스페이스에 AGENTS.md 가 있을 때만 뜹니다(없으면 2개만 뜸).
> ③ **용도 확인** (`I am using this for local development`) → **1번** 선택.
> 셋 다 지나야 Slack 채널이 이 세션에 연결됩니다. 화면이 이 안내와 다르면 그 자리에서 알려주세요."
>
> ⚠️ **3연속은 «최초 설치» 한정이다** — 세션을 재기동하면 ①②는 이미 기억돼 있어 ③만 뜬다(2026-08-06 WSL 재기동 실측). "왜 이번엔 하나만 뜨지"도, "왜 처음엔 셋이나 뜨지"도 둘 다 정상이다.
>
> (2026-08-06 WSL 라이브 실측 — 결함 12: 구 안내는 ③ 하나만 예고해, 3연속으로 뜨자 "뭔가 잘못됐나" 정지를 유발했다. ①은 Step 12 가 만든 `.mcp.json` 의 최초 승인, ②는 Step 7-A ③ 이 박은 `@../AGENTS.md` import 가 부르는 창 — 인과가 스킬 안에 있으므로 안내도 스킬이 진다.)

### Step 15. 검증 [자동] + [반자동]

**자동 확인**(전부 Step 8이 정한 `$STATE_DIR` 기준 — 기본 경로로 확인하면 **다른 봇 것을 보고 통과 판정**한다):
1. 소켓·pidfile 존재 — `$STATE_DIR/primary.sock`, `$STATE_DIR/primary.pid`
1-b. **pidfile 의 pid 가 방금 띄운 프로세스인가** — 추가 봇인데 첫 봇의 pid 를 보고 "떠 있다"로 읽으면 **아무것도 안 띄우고 GREEN** 이 된다
2. 서버 로그에 `bridge live — channel ..., allowed user ...` 라인 매칭 — 없으면 기동 실패, 로그 tail 그대로 사용자에게 제시
3. `.env` mode 600 + 필수 키 4개
4. `.mcp.json`이 유효 JSON이고 `mcpServers.slack-channel` 키 존재
5. ~~`slack manifest diff`로 로컬↔원격 매니페스트 일치 확인~~ → **[2026-08-06 실측 폐기]** 웹 매니페스트 경로로 만든 앱은 CLI 프로젝트 컨텍스트가 없어 `slack manifest info/diff` 가 `installation_required` 로 돈다(결함 5 순환과 동일). 매니페스트 «선언» 대조는 포기하고, 아래 6-b 의 «부여» 실측이 그 자리를 대신한다 — 어차피 중요한 건 선언이 아니라 토큰이 실제로 들고 있는 권한이다.
6. 봇 토큰 자가진단(claude-channel-server 자체엔 이 커맨드가 없다 — 스킬이 셸에서 직접 수행): `curl -H "Authorization: Bearer $BOT_TOKEN" https://slack.com/api/auth.test` → `ok:true` 확인
6-b. **부여 scope 재확인 — [Step 10-c](#step-10-c-부여-scope-관문-자동--부족하면-여기서-정지-다음-단계로-넘어가지-않는다) 와 같은 검사를 그대로 재실행한다**(정본 블록은 10-c 하나 — 사본을 두지 않는다). 설치 후 사용자가 앱 설정을 바꿨거나 재설치로 토큰이 회전된 경우를 여기서 다시 잡는다.

**반자동 확인(사람 확인 필요)**:

> "Slack에서 방금 만든 봇에게 DM으로 아무 말이나 보내보세요. 잠시 후 이 세션에 그 메시지가 보이고, 제가 답장하면 Slack에도 표시됩니다. 안 되면 알려주세요."

### Step 15-A. 인격·거버넌스 주입 검증 — cwd 체인로드는 훅과 다른 실행이다 [검증]

> 파일이 있는 것과 실제로 응답에 반영되는 것은 다르다(create-bot의 "soul.md 주입 검증" 절과 같은 원칙). 단 Slack 판은 메커니즘이 다르다 — SessionStart 훅이 아니라 **Step 7-A가 만든 CLAUDE.md의 cwd 체인로드**이므로, 검증도 그 경로를 겨냥해야 한다. 아래 체크리스트의 "CLAUDE.md 실제 주입 검증" 항목이 가리키는 절차가 이것이다.

**① 음성 대조 항목을 미리 정한다**: `$BOT_DIR/soul.md`(또는 CLAUDE.md 페르소나 절)에 **없는** 항목 하나를 골라둔다(예: "좋아하는 음식").

**② Step 13-A/14로 기동된 세션에 그대로 보낸다**(파일을 직접 열어 커닝하지 못하게 막는 것이 핵심):

```
파일을 절대 읽지 말고(Read·grep·cat 금지) 지금 컨텍스트에 있는 것만으로 답하라:
  ① 네 이름과 역할   ② 완료 시 서명(있다면)   ③ 이 세션의 Working Directory
  ④ (음성 대조) 네 페르소나에 적힌 <미리 정한 항목> — 없으면 없다고
각 항목에 ⓐ주입됨 / ⓑ기억 안 남 라벨을 붙여라.
```

**③ 판정**:
- ①②③이 Step 7-A에서 만든 `$BOT_NAME`·`$ROLE_DESC`·`$BOT_DIR`와 일치하고, ④가 정직하게 "없다"고 답하면 **GREEN**. ④에서 지어내면 나머지 답도 "그럴듯하게 구성한 것"이지 주입 증거가 아니므로 시험 전체 무효(create-bot과 동일 원칙).
- **①에서 다른 봇 이름(예: Andre Karpathy 등 워크스페이스 상위 CLAUDE.md의 봇 메타)이 나오면** = cwd가 봇 루트 폴더가 아니었다는 뜻이다 — Step 13-A/14를 다시 확인한다. `04-handoff.md` §3.4가 실측한 것과 동일한 증상(CLAUDE.md 없는 폴더에서 기동 → 정체성이 상위로 fallback)이다.

⚠️ **타임아웃을 넉넉히**: 헤드리스 1문(`claude -p`)이 훅·플러그인이 무거운 환경에서 8분까지 걸린 실측이 있다(2026-08-06 루돌프 WSL: 180초 타임아웃 실패 → 480초 통과). 자동 게이트로 쓸 땐 타임아웃 ≥ 600초로 잡는다.

**④ 실 ID 되채움**: Step 7-A ②-b에서 `(Step 15-A에서 실측 기입)`으로 남긴 자리(봇 user ID 등)를 이 시점에 실측값으로 치환한다 — 브리지가 기동돼 있으므로 봇 토큰 `auth.test` 응답의 `user_id`가 정답이다(값을 지어내지 않는다). 치환 후 `command grep -n '실측 기입' "$BOT_DIR/soul.md" "$BOT_DIR/CLAUDE.md"` 재검 → 잔존 마커 0이어야 완료.

---

## 검증 체크리스트

- [ ] **`$STATE_DIR` 이 의도한 폴더인가** — 추가 봇인데 기본 경로면 첫 봇을 덮은 것이다(가장 먼저 본다)
- [ ] 기존 봇이 있었다면 **그 봇이 아직 살아있는가**(`kill -0` + Slack 왕복 1회) — 새 봇을 만들며 남의 봇을 죽이지 않았다는 증명
- [ ] `$STATE_DIR/.env` 존재 + chmod 600 + 필수 키 4개 + 키당 줄 1개(중복 없음)
- [ ] resident server 로그에 `bridge live — channel ..., allowed user ...`
- [ ] `.mcp.json`에 `mcpServers.slack-channel` 등록
- [ ] `slack manifest diff` 로컬↔원격 일치
- [ ] `curl auth.test` → `ok:true`
- [ ] Slack DM → 세션에 메시지 도착 → `reply` 도구 응답 → Slack에 표시 ✅
- [ ] **`$BOT_DIR`(Step 7-A) 가 실제 cwd 로 세션이 떴는가** — Step 13-A/14 확인. 어긋나면 아래 항목이 통째로 무의미하다(가장 먼저 본다)
- [ ] `$BOT_DIR/CLAUDE.md` 존재 + 봇 메타·정체성 우선순위 가드·페르소나 절 포함
- [ ] (페르소나 입혔다면) **CLAUDE.md 실제 주입 검증** — 위 [Step 15-A](#step-15-a-인격거버넌스-주입-검증--cwd-체인로드는-훅과-다른-실행이다-검증) 절차(파일 존재 ≠ 주입, 음성 대조 필수 — **메커니즘은 create-bot과 다르다**: SessionStart 훅이 아니라 cwd 체인로드)

---

## 트러블슈팅

| 증상 | 1순위 원인 | 대응 |
|---|---|---|
| `npm run build` → `Missing script: "run"` | 셸 래퍼·프록시(토큰 절약 도구 등)가 `npm run` 을 다른 명령으로 재작성 — 번들 결함 아님(package.json 에 `build` 스크립트 실재, 2026-08-06 WSL 실측) | 우회: `./node_modules/.bin/tsc -p tsconfig.json` 직접 실행(= `build` 스크립트의 실체). `npm start` 가 같은 증상이면 `node dist/server.js` 직접 실행 |
| `slack: command not found` (Step 1 자동 설치 후에도) | ①네트워크가 `downloads.slack-edge.com`에 못 닿음 ②설치는 됐는데 `$HOME/.local/bin`이 PATH에 없음(Step 1 이 프로필 영구 등록까지 자동 수행하나, 비표준 프로필 구성이면 빗나갈 수 있음) | ①curl 에러 메시지 확인(프록시·방화벽) ②`export PATH="$HOME/.local/bin:$PATH"`를 실제 사용하는 셸 프로필에 직접 추가 후 새 셸 재시작 ③그래도 안 되면 공식 문서의 수동 tar.gz 설치(sudo 불요) — [설치 가이드](https://docs.slack.dev/tools/slack-cli/guides/installing-the-slack-cli-for-mac-and-linux/). 🔴 `sudo apt install`류로 우회하지 말 것 — 무-sudo 환경(WSL 등)에서 관문 앞 탈락 재현됨(2026-08-06 실측) |
| DM 보냈는데 반응 0 | `message.im` 이벤트 미구독 | Step 4 매니페스트 `bot_events`에 `message.im` 있는지, `slack manifest diff`로 원격 반영 재확인 |
| DM 반응 0(이벤트는 옴, 로그엔 찍힘) | `ALLOWED_SLACK_USER_ID` 불일치 | 보낸 사람의 실제 Slack user ID와 `.env` 값 대조(`slack auth list`가 아니라 DM 보낸 계정 기준) |
| 채널 메시지만 무반응(DM은 됨) | 채널 게이트 불일치 | `.env`의 `SLACK_CHANNEL_ID`와 실제 채널 ID 대조(`server.ts:299`) |
| `npm start` 즉시 에러 종료 | 싱글톤 가드 — **대개 `STATE_DIR`이 다른 봇 폴더로 떨어진 것** | ①`$STATE_DIR` 확인 → 추가 봇인데 기본 경로면 Step 8 재실행 ②그 pid 가 남의 봇이면 **끄지 말고** 폴더를 나눈다 ③진짜 stale 이면 그 pidfile 만 정리 |
| 새 봇을 만들었더니 **기존 봇이 죽거나 말이 없어짐** | `STATE_DIR` 공유 — 기존 `.env`가 Step 10 truncate 로 지워짐 | 즉시 중단. 기존 봇 토큰 재발급 후 **그 봇 전용 폴더**로 복구, 새 봇은 별도 폴더로 다시. Step 8 점유 검사가 이걸 막는 장치다 |
| A봇 세션인데 **B봇 Slack 으로 답이 나감** | `.mcp.json`의 `env.CLAUDE_CHANNEL_SLACK_DIR` 누락 → MCP가 기본 소켓에 붙음 | Step 12의 `env` 줄 확인. 에러가 안 나므로 증상으로만 판별된다 |
| `.env` 관련 경고 로그 | mode ≠ 0600 | `chmod 600 "$STATE_DIR/.env"` |
| `channelsEnabled` 조직 정책이 꺼져 있음 | 조직 정책 | Console/API-key는 기본 켜짐. claude.ai Team/Enterprise는 Owner가 켜야 함 |
| Linux/WSL에서 이 브리지를 씀 | (2026-08-06 이전엔 peer-UID 체크가 macOS 전용이라 모든 IPC 연결이 조용히 거부됐다) 지금은 `SO_PEERCRED` 경로로 정상 지원 대상 — 단 실제 워크스페이스 왕복은 **미검증**(코드 정합성까지만 확인) | 그래도 안 되면 `libc.so.6`(glibc) 로드가 되는지부터 확인 — 로드 자체가 실패하면 여전히 fail closed로 거부된다 |
| `--dangerously-load-development-channels`의 1회 확인 다이얼로그를 놓침 | 관문 E 미확인 | 첫 기동 시 다이얼로그에서 승인 필요 |

---

## ThisCodex 대응 차이 (요약 — 상세는 ThisCodex 쪽 문서 참조)

Codex 판은 이 스킬을 그대로 이식할 수 없다:
- **프로토콜**: 공식 `claude/channel` MCP(이쪽) vs 비공식 커스텀 — `codex app-server` WebSocket JSON-RPC 위의 별도 Slack Bolt 브리지(ThisCodex)
- **"채널 등록" 대응 개념 부재**: `.mcp.json` + `--dangerously-load-development-channels` 같은 것이 없다 — 대신 상주 `codex app-server --listen ws://...`를 별도로 기동해야 하는데, 그 기동 스크립트 자체가 아직 없다
- **토큰 전달 계약이 근본적으로 다르다**: 이쪽은 정적 `.env`를 브리지가 직접 로드하지만, Codex 쪽은 **실행 중인 `slack run` 프로세스의 env를 `ps eww`로 읽어** 그때그때 토큰을 회수한다 — 위 토큰 캡처·`.env` 검증 단계(Step 10~11)를 그대로 복붙할 수 없다
- **매니페스트(Step 4)만은 구조가 거의 같아** 재사용 여지가 크다

## 미결·리스크 (정직 표기 — 2026-08-06)

1. **[해소 — 2026-08-06 루돌프 WSL round 3 실측] CLI 앱 생성 경로는 검증이 아니라 폐기로 닫혔다** — `slack create --template blank` 부재(`template_path_not_found`) · `manifest sync` 는 `--experiment manifest-sync` 요구 · sync↔install 순환(`installation_required`) · `app install` 은 TTY 프롬프트 2중(비대화형 진입점 없음). 그래서 Step 4~5 를 **웹 매니페스트 경로(관문 B)** 로 재설계했다. 잔여 미검증 = 웹 경로 관문 B 의 라이브 통과(앱 생성→설치→App ID→토큰 발급 연쇄).
2. **[해소 — 같은 실측]** 구 "`manifest sync -f` 비대화형 보장 미검증" 항목: 실제 문제는 `-f` 가 아니라 experiment 플래그 의존이었고, 경로 폐기로 항목 자체가 소멸.
3. **채널 자동 초대(Step 9)의 스코프 미확정** — `conversations.join`에 필요한 정확한 스코프명은 Slack 공식 문서 대조가 필요하다. 스코프를 추가하면 매니페스트가 다시 바뀌어 재설치(재승인) 관문이 한 번 더 발생할 수 있다. ~~이름→ID 변환의 `conversations.list` 대안 경로도 같은 이유로 스코프가 아직 없다~~ → **[부분 해소 — 2026-08-06 WSL 라이브 실측]** `conversations.list` 는 현 매니페스트로 `missing_scope`(needed: `channels:read,groups:read,mpim:read,im:read`) 확정 — 기본 경로(사용자에게 직접 확인)가 정답으로 확정(Step 9 항목 3). 자동 초대 스코프명만 미확정으로 남는다.
4. **`ALLOWED_SLACK_USER_ID` 자동 제안의 전제** — `slack auth list`가 반환하는 로그인 계정을 "이 봇을 쓸 사람"으로 가정한다. 다른 사람이 이 머신에서 CLI 로그인을 해뒀다면 오탐 가능 — 입력 계약 #6에서 제안만 하고 사람 확인 1클릭을 반드시 거치게 설계했다.
5. **마켓플레이스 플러그인 배포 경로 미구현** — README가 언급하는 `claude --channels plugin:slack-channel@your-marketplace` 경로는 실물이 없다. 이 스킬은 현재로선 `--dangerously-load-development-channels` 경로만 다룬다.
6. **`messages_tab_read_only_enabled: false` 정정이 필요·충분한지 미검증** — 필드 이름에 대한 추론이며, 라이브 토글 재현으로 확정한 적은 없다.
7. **(신설, ㉡ 인격·거버넌스) Step 7-A의 `@../AGENTS.md` import는 "봇 폴더가 워크스페이스 루트의 직속 하위"라는 가정에 의존한다** — 사용자가 봇 폴더를 더 깊은 경로(예: `bots/<name>/`)에 두면 상대경로가 어긋난다. 지금은 `$WORKSPACE_ROOT/${BOT_NAME}` 고정 1단계 깊이만 다룬다.
8. **SessionStart 훅(`bot-session-init.sh`) 확장은 이번 패치 범위 밖이다(의도적)** — Slack 상태 디렉토리를 훅이 인식하도록 고치는 경로(D-2′)는 재경님 결정 대기 항목이라, 이번 Step 7-A는 훅에 의존하지 않는 CLAUDE.md 직접 임베드로 우회했다. 훅 확장이 나중에 결정되면 이미 만들어 둔 `soul.md` 사본을 그 경로가 대신 읽도록 전환할 수 있다 — 지금 상태에서 재작업이 크지 않다.
9. **`$BOT_NAME`(Step 0-A, 폴더·CLAUDE.md용)과 Step 8의 추가 봇 slug(상태 폴더용)가 강제로 같지 않다** — 같은 값을 쓰면 폴더 이름과 상태 폴더 이름이 맞아 추적이 쉽지만, 이 스킬은 둘의 일치를 강제하지 않는다(동작에는 지장 없음).
10. **두 번째 이상 봇 생성 시 워크스페이스 루트에 이미 `<bot-name>` 폴더가 있으면 Step 7-A가 멈춘다** — 사람이 다른 이름을 고르는 것이 정상 경로다(Step 8이 상태 폴더 충돌에서 쓰는 것과 같은 원칙: 끄거나 덮지 않고 나눈다).

## 관련 자원

- 기술 참고서(프로토콜·아키텍처·보안 모델·함정 목록): [../slack-bridge/SKILL.md](../slack-bridge/SKILL.md)
- Discord 판(공유 로직의 정본): [../create-bot/SKILL.md](../create-bot/SKILL.md)
- 근거: `claude-channel-server` 소스(`README.md`·`src/config.ts`·`src/server.ts`) · Slack CLI v4.6.0 실측 · 내부 설계 기록(비공개)
