---
name: slack-bridge
description: Use when connecting a Claude Code session to Slack via the official claude/channel MCP protocol. Covers the resident claude-channel-server bridge (Slack Socket Mode + Unix domain socket), the per-session MCP stdio proxy, DM + channel + user-driven thread support, the permission-relay pattern, and round-trip verification. Codex CLI has a separate, protocol-different Slack bridge — see ThisCodex's slack-bridge SKILL.md for that.
---

# Slack Agent Bridge — Claude Code ↔ Slack (공식 `claude/channel` 프로토콜)

> codex 짝 문서 = ThisCodex `skills/slack-bridge/SKILL.md`. 겉보기엔 "같은 걸 두 엔진으로" 처럼 보이지만 **프로토콜부터 다르다** — 이쪽은 Claude Code 공식 채널 프로토콜(MCP), codex 쪽은 Slack Bolt Python·로컬 엔진 호출이다. 코드도 완전히 분리된 별도 프로젝트이고, 이 문서는 codex를 다루지 않는다. **교차 갱신 계약**: Slack scope의 선언↔실부여·재설치 의미, 검증 급, 보안 경계처럼 공유되는 사실은 양쪽에 동시에 반영하고, 구현 고유 코드·실행 환경(엔진별 샌드박스·플래그 등)은 각 소유 문서에만 둔다.

Claude Code 세션이 Slack 채널·DM 메시지를 자기 컨텍스트로 직접 받고, `reply` 도구로 그 대화에 답하게 만드는 공정이다. 핵심은 **브리지가 Claude Code CLI를 대신 실행해주는 게 아니라는 것** — 이미 떠 있는 Claude Code 세션에 Slack이라는 채널 하나를 "연결"하는 것뿐이다(공식 채널 프로토콜, [channels-reference](https://code.claude.com/docs/en/channels-reference)).

## ⚠️ 시작하기 전 — 브리지 소스는 번들에 동봉됨 (2026-08-06 결정 · vendor 동봉)

이 브리지의 실제 코드(`claude-channel-server`)는 **`vendor/claude-channel-server/`에 ThisCode 번들 안에 동봉되어 있다**(배포 결정). 소스만 있고 `dist/`(빌드 산출물)는 레포에 안 들어있다 — `.gitignore`가 명시적으로 제외한다(소스↔빌드본 drift 방지: 고치고 빌드 안 하면 옛 `dist`가 계속 도는 사고를 막기 위해서다). `slack:configure` 스킬의 Step 0이 이 vendor 경로를 기본값으로 찾고, `npm install && npm run build`를 자동 실행해 그 자리에서 `dist/`를 만든다.

> 🔴 **라이선스 미확정(미해결)**: `vendor/claude-channel-server/package.json`에 `"license"` 필드가 없고(`"private": true`만 있음), 별도 `LICENSE` 파일도 없다 — 원본 소스 그대로 동봉했기 때문이다. ThisCode 루트 자체는 MIT(`LICENSE`, `package.json` `"license": "MIT"`)이지만, 동봉된 이 코드에 같은 라이선스를 적용할지는 **저작권자(재경님) 결정 사안**이라 아직 정하지 않았다 — 워커가 임의로 라이선스를 지어 넣지 않는다. 결정 전까지는 이 상태 그대로 두고, 결정되면 이 절과 `vendor/claude-channel-server/LICENSE`(필요시)·`package.json`을 갱신한다.

## 아키텍처

```
Slack  <--Socket Mode-->  server.ts (resident)  <--Unix socket-->  mcp.ts (per-session)  <--stdio (MCP)-->  Claude Code 세션
```

두 프로세스로 나뉜다:

1. **`server.ts`** — 상주 프로세스. 실제 Slack Socket Mode 연결과 Unix domain socket(`$STATE_DIR/primary.sock` — 기본값 `~/.claude/channels/slack/`)을 **그 폴더에 대해** 이 프로세스 하나만 쥔다. 한 번 띄워두고 계속 둔다. 봇이 여러 개면 폴더가 여러 개고 상주 프로세스도 봇마다 하나씩이다(§ 싱글톤 가드).
2. **`mcp.ts`** — 얇은 MCP stdio 프록시. Claude Code가 세션마다 하나씩 스폰한다. 자기 Slack 자격증명이나 Socket Mode 연결이 없고, `server.ts`와 Unix 소켓으로만, Claude Code와는 stdio로만 말하며 그 사이를 번역한다.

이렇게 나눈 이유: Slack 앱 연결 하나로 열려 있는 모든 Claude Code 세션을 같이 서비스하기 위해서다 — 세션마다 자기 Socket Mode 연결을 새로 열면 Slack이 한 앱에 대해 다중 연결을 rate-limit/flapping 시키기 시작한다(README.md).

⚠️ **정직 표기**: 서버는 상태를 안 갖는 릴레이다 — 어느 스레드가 어느 세션과 짝인지 브리지가 파일로 관리하지 않는다. 인바운드 메시지는 연결된 모든 `mcp.ts` 프록시(=열려 있는 모든 세션)에 그대로 브로드캐스트된다. "이 스레드는 이 세션"이라는 매핑은 Claude Code 세션 자신이 채널 프로토콜 레벨에서 담당한다 — 세션 여러 개를 동시에 같은 Slack 채널에 붙였을 때 누가 응답할지는 이 브리지 밖의 관심사다.

## 전제

- Node.js + npm (claude-channel-server는 TypeScript 프로젝트 — `npm run build`로 `dist/`에 컴파일)
- Slack 워크스페이스 = 본인이 앱을 설치할 권한이 있는 곳
- 로컬에 `claude`(Claude Code) 설치·로그인 상태 + 조직의 `channelsEnabled` 정책이 켜져 있을 것(Console/API-key 사용은 기본 켜짐, claude.ai Team/Enterprise는 Owner가 켜야 함, org 없는 Pro/Max는 검사 없음 — README.md:66)
- claude-channel-server 소스 체크아웃: **`vendor/claude-channel-server/`에 ThisCode 번들 git-tracked로 동봉되어 있다**(2026-08-06 vendor 동봉 결정) — 소스만 있고 `dist/`는 없다(`.gitignore` 제외). `slack:configure` 스킬 Step 0이 이 번들 경로를 기본값으로 확인하고, `npm install && npm run build`를 자동 실행해 `dist/`를 그 자리에서 만든다 — 사람이 따로 체크아웃을 준비할 필요가 없다. 다른 위치의 별도 체크아웃을 쓰고 싶으면 Step 0에서 경로를 지정하는 폴백이 있다. README가 언급하는 마켓플레이스 플러그인 배포 경로(`claude --channels plugin:slack-channel@your-marketplace`)는 아직 구현되지 않았다 — 현재 실물은 `--dangerously-load-development-channels` 로컬 개발 경로뿐이다.

> **포털(api.slack.com) 매니페스트로 앱을 만든다** — Slack CLI(`slack create`/`slack run`)의 대화형 마법사만으로 앱을 완성하지 않는다. claude-channel-server는 process manager도 자동 설치도 내장하지 않는 순수 Node 라이브러리라, 앱 자체는 Slack 표준 매니페스트 플로우로 만든다. 이 판단·매니페스트 생성/동기화·이후 전 설치 공정은 아래 '셋업' 절에서 설명하는 `slack:configure` 스킬이 대신 수행한다.

## 셋업 — 자동 최대 + 사람 관문에서만 질문 (`slack:configure` 스킬이 실행)

> 원칙(2026-08-06 결정, 원문 인용): "무조건 자동으로 최대한 되게 하고, 수동으로 하거나 막히는 지점, 단계별로 할 게 있으면 사용자에게 질문하거나 가이드를 주는 방식이어야 합니다." 이 절은 그 원칙이 구현된 결과를 설명하는 참고서다 — 아래 흐름을 손으로 따라 치지 않는다. **실제 설치·설정 실행은 `slack:configure` 스킬**(`skills/slack-configure/SKILL.md`)이 사전 점검부터 resident server 기동·최초 검증까지 맡는다.

**자동 10단계**(사람 개입 없이 진행): 사전 점검 + **Slack CLI 부재 시 자동 설치**(`slack --version` 없으면 공식 설치 스크립트로 sudo 없이 홈 디렉토리에 설치, 2026-08-06 F1 — WSL 등 무-sudo 환경 실측 반영) + `node -v`·소스 위치 확인 → 기존 Slack CLI 인증 확인 → 매니페스트 파일 생성(아래 예시 — 앱 생성 자체는 웹 매니페스트 관문, CLI 앱 생성·`manifest sync` 경로는 2026-08-06 실측으로 폐기: TTY 프롬프트·experiment 플래그·순환 의존) → 브리지 설치(`npm install && npm run build`) → 상태 디렉토리 준비(`~/.claude/channels/slack`, `chmod 700`) → 채널 확보(이름 → ID 변환) → `.env` 검증(필수 키 4개 + mode 600) → `.mcp.json` 등록 → resident server 기동(`npm start`).

**사람 관문 4개 + 조건부 1개** — 자동화로 없앨 수 없는 지점. 스킬이 여기서만 멈춰 안내하고 기다린다(발생 순서대로):

| 관문 | 무엇을 하나 | 왜 사람이어야 하나 |
|---|---|---|
| A — Slack CLI 로그인 | 티켓 확인 후 챌린지 코드 입력 | 계정 인증은 본인만 할 수 있다 |
| B — 워크스페이스 설치 승인 | 브라우저에서 "허용(Allow)" 클릭 | OAuth 권한 승인은 계정 소유자 행위 |
| C(조건부) — 메시지 탭 켜기 | App Home → Messages Tab 토글 — **B 직후, 매니페스트 자동 반영이 이 설정까지 못 따라갔을 때만 발동**(평소엔 안 뜬다) | Slack 쪽 UI 토글이라 사람이 직접 켜야 한다 |
| D — 토큰 값 입력 | Bot Token(`xoxb-`)·App Token(`xapp-`)을 클립보드 경유로 저장 | 토큰 값은 화면에서 사람이 직접 복사해야 나온다 |
| E — 최초 채널 로드 확인 | 확인 창 **최대 3연속**: ①MCP 서버 승인(`.mcp.json`) ②외부 import 허용(`@../AGENTS.md`, 있을 때만) ③"I am using this for local development" — 전부 1번 선택 | Claude Code 최초 1회 안전 확인 다이얼로그 (3연속 인과·권장값 = slack-configure Step 14 정본) |

셋업이 끝나면 다음이 자동으로 확인된다(`slack:configure` 검증 단계): 소켓·pidfile 존재, 서버 로그의 `bridge live — channel ..., allowed user ...` 라인, `.env` mode 600 + 필수 키 4개(`SLACK_BOT_TOKEN`·`SLACK_APP_TOKEN`·`ALLOWED_SLACK_USER_ID`·`SLACK_CHANNEL_ID` — `config.ts` `REQUIRED_KEYS`), `.mcp.json` 유효성, **부여 scope 실측(선언 전부, 현 템플릿 5종)**(`auth.test` 응답 헤더 `x-oauth-scopes` 대조 — 선언 ≠ 부여, 2026-08-06 결함 15: `im:history` 미부여 시 `message.im` 이 애초에 안 와서 DM 이 무징후로 죽는다. 구 「매니페스트 로컬↔원격 일치」 확인은 웹 경로 앱에서 CLI 가 `installation_required` 로 돌아 폐기). 상태 디렉토리는 `CLAUDE_CHANNEL_SLACK_DIR` 환경변수로 바꿀 수 있고 기본값은 `~/.claude/channels/slack/`이다.

⚠️ **싱글톤 가드**: 같은 상태 폴더에 이미 살아있는 인스턴스가 있으면 두 번째 `npm start`는 즉시 에러로 죽는다(`singleton.ts` — pidfile `$STATE_DIR/primary.pid` + liveness 체크). 버그가 아니라 의도된 가드다 — 안 걸리게 두면 두 번째 프로세스가 첫 번째의 소켓 파일을 지우고 뺏어가 인바운드가 두 프로세스로 조용히 쪼개진다(`singleton.ts:1-6` 주석).

🔴 **한 기계에 봇 2개 이상 = 상태 폴더를 나눈다.** 가드는 **폴더당** 하나를 강제하는 것이지 **기계당** 하나가 아니다. 추가 봇은 `CLAUDE_CHANNEL_SLACK_DIR=~/.claude/channels/slack-<이름>` 으로 띄운다 — `.env`·소켓·pidfile 이 전부 그 아래로 따라간다(`config.ts:14-17`).
- **가드에 걸렸다고 살아있는 프로세스를 끄지 마라.** 그건 남의 봇이다. 정상 경로는 폴더를 나누는 것이고, 끄는 건 사용자 결정이다.
- **server 와 MCP 양쪽에 같은 값을 줘야 한다** — `.mcp.json`의 `env.CLAUDE_CHANNEL_SLACK_DIR` 이 빠지면 MCP(`mcp.ts:17,146`)가 **기본 폴더 소켓**에 붙어 "A봇 세션이 B봇 Slack 에 답하는" 엇갈림이 된다. **에러가 안 난다** — 증상으로만 보인다.
- 자동 셋업은 `/thiscode:slack-configure` Step 8 이 점유 검사로 이 분기를 처리한다(2026-08-06 신설 — 그전 판본은 기본 경로를 박아둬 **두 번째 봇 생성이 첫 봇의 `.env` 를 truncate** 했다).

### 매니페스트 예시 (`slack:configure`가 자동 적용 — 참고용)

DM이 실제로 되려면 `messages_tab_enabled: true`가 필수다(과거 매니페스트는 `false`인 채 라이브 drift로 남아있던 사례 실측 — 2026-08-06). 이벤트는 `message.im`·`message.channels`·`app_mention` 셋 다, 스코프는 `chat:write`·`im:history`·`channels:history`·**`app_mentions:read`**(`app_mention` 이벤트의 요구 스코프 — 빠지면 `invalid_manifest`, 2026-08-06 실측)·`reactions:write`(react 도구 — 이모지 반응, 2026-08-06 추가), Socket Mode on. 토큰·팀 ID 등 비밀값은 매니페스트에 없다 — `.env`가 시크릿의 유일한 자리다(`config.ts:53-90`).

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
      "display_name": "<멘션 핸들 — 예: claudetofu. 🔴 영문 권장(ASCII) — @자동완성은 한글 표시명도 잡히지만(2026-08-07 라이브 재실측) 미초대·이름 반영 직후엔 안 뜨는 사례가 있어(2026-08-06 오전 실측), 이 영문 핸들이 항상 되는 확실한 경로다>",
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

⚠️ `messages_tab_read_only_enabled: false`는 필드 이름에 대한 추론으로 정정한 값이다(DM 왕복 = 사용자가 타이핑해야 하니 read_only도 함께 꺼야 한다는 판단) — 라이브 토글 재현으로 확정한 적은 없다. `shortcuts`·`slash_commands`·`commands` 스코프는 이 브리지 코드가 안 쓰는 Bolt-starter 잔재라 지워도 무해하다.

## Claude Code 세션에 채널 등록

`.mcp.json`에 MCP 서버로 등록(`slack:configure`가 자동 수행 — 아래는 축약 예시. **`env.CLAUDE_CHANNEL_SLACK_DIR`을 빼지 말 것** — 위 "🔴 한 기계에 봇 2개 이상" 절의 경고와 동일 이유, 실제로 스킬이 쓰는 전문은 `slack-configure/SKILL.md` Step 12):

```json
{
  "mcpServers": {
    "slack-channel": {
      "command": "node",
      "args": ["/absolute/path/to/claude-channel-server/dist/mcp.js"],
      "env": { "CLAUDE_CHANNEL_SLACK_DIR": "<상태 폴더 절대경로 — 기본 ~/.claude/channels/slack/>" }
    }
  }
}
```

🔴 **이 `.mcp.json`은 세션의 cwd 안에 있어야 로드된다.** `slack:configure`가 만드는 봇은 cwd가 봇 전용 루트 폴더(WD)이므로 — 빈 `session/` 폴더가 아니다(2026-08-06 D-2 확정, `slack-configure/SKILL.md` Step 7-A·13-A) — `.mcp.json`도 **그 WD 안**에 둔다. WD와 이 파일 위치가 어긋나면 아래 채널 등록 자체가 안 먹는다.

그리고 그 WD를 cwd로, 채널을 opt-in한 상태로 Claude Code를 켠다:

```bash
# 로컬 개발(이 문서 기준 경로) — 이걸 쓴다. cwd = 봇 WD(위 참고)
cd "<봇 WD>"
claude --dangerously-load-development-channels server:slack-channel

# 마켓플레이스에 플러그인으로 배포한 뒤라면
claude --channels plugin:slack-channel@your-marketplace
```

`--dangerously-load-development-channels`는 최초 1회 확인 다이얼로그("I am using this for local development", 위 관문 E)를 띄우고 플러그인 allowlist 검사만 우회한다 — 위 `channelsEnabled` 조직 정책 자체는 이걸로도 못 우회한다(README.md:66).

메시지가 도착하면 세션 컨텍스트에 이렇게 보인다:

```
<channel source="slack" channel="C0000..." user="U0000..." ts="..." thread_ts="...">
your message text
</channel>
```

## 응답 (`reply` 도구) · 반응 (`react` 도구)

`mcp.ts`가 노출하는 도구는 둘이다(2026-08-06 `react` 추가 — 재경님 요청 "응답때 이모지로 반응"):

**`reply`** — 메시지 발신:

| 인자 | 필수 | 설명 |
|---|---|---|
| `text` | ✅ | 보낼 메시지 |
| `chat_id` | – | 인바운드 `<channel>` 태그의 `channel` 속성을 그대로 echo(DM은 `D…`, 채널은 `C…`). 생략하면 가장 최근 인바운드가 온 대화로 폴백 |
| `thread_ts` | – | 인바운드 태그의 `thread_ts`를 그대로 echo하면 그 스레드로 답한다. 생략하면 새 top-level 메시지 |

**`react`** — 이모지 반응(`reactions.add`, `reactions:write` 스코프 필요):

| 인자 | 필수 | 설명 |
|---|---|---|
| `chat_id` | ✅ | 인바운드 태그의 `channel` 속성 echo — reply 와 달리 폴백이 없다(반응은 "가장 최근 대화" 추정이 위험) |
| `message_ts` | ✅ | 반응을 달 메시지의 `ts`(인바운드 태그의 `ts` echo) |
| `emoji` | ✅ | 이모지 이름 — `thumbsup`·`:tada:` 둘 다 허용(양끝 콜론은 서버가 벗긴다). 같은 이모지 중복 반응(`already_reacted`)은 성공으로 취급 |

react 도 reply 와 같은 outbound allowlist 를 탄다 — 인바운드를 받은 적 있는 대화에만 반응할 수 있다(미지의 대화에 반응 = 존재 누출).

**scope 함정(공유 사실 — ThisCodex 판과 동시 갱신 계약)**: manifest 의 `reactions:write` 는 **선언**이고, 이미 설치된 앱 토큰의 **실부여**가 아니다 — 선언 추가 후 재설치(승인 목록에 `reactions:write` 가 보이는)까지 해야 토큰에 붙는다. 순서 함정 실측(2026-08-08): 선언 없이 재설치를 먼저 승인하면 scope 는 그대로다 — **선언이 항상 먼저**. `react` 콜백은 `missing_scope` 를 조용히 건너뛰므로 이 함정에 빠져도 메시지 응답 본선은 계속 동작한다(= 무징후 — scope 는 `auth.test` 응답 헤더 `x-oauth-scopes` 로 실측하라). 라이브 e2e 검증 기록: ThisCodex 판(Bolt Python)은 2026-08-08 GREEN(반응+정상 답변 동시 확인) — 본 판(MCP `react`) 자체의 라이브 계측 기록은 아직 없다.

## DM · 채널 · 사용자주도 스레드 (실제 동작 — 2026-08-06 정정)

- **채널 게이트**(`server.ts` `handleSlackEvent`, L299): `event.channel === SLACK_CHANNEL_ID` **이거나** `event.channel_type === 'im'`(DM)이면 통과. 그 외는 버림.
- **발신자 게이트 — 저자 종류로 분기**(L310~, 2026-08-07 (B) 봇간 통신 이식): `bot_id`(또는 `subtype === 'bot_message'`) 유무로 사람/봇을 가른 뒤 —
  - **사람 경로**: `event.user === ALLOWED_SLACK_USER_ID` 아니면 버림(채널·DM·@멘션·승인 답장 전부 이 한 checkpoint 공유), `subtype`(수정·입장 등) 버림. 사람 발화는 그 스레드의 봇 왕복 예산을 리셋한다.
  - **봇 경로**(전부 만족해야 통과): ①DM 아님(봇간 DM 금지 — DM 경로의 보안 논거는 «검증된 사람과 1:1») ②자기 에코 아님 + `user`(U…) 존재 ③`ALLOWED_SLACK_BOT_USER_IDS` 목록에 있음(**미설정/빈 값 = 봇 전면 차단 = 이식 전과 동일 — 기존 설치 회귀 0**) ④본문에 `<@이봇ID>` 명시 멘션(승인 답장 우회·스레드 면제 둘 다 봇에겐 없음 — VERDICT_PATTERN 은 anchored 라 멘션과 공존 불가 = 허용 봇도 권한 승인은 구조적으로 불가). **왕복 횟수 상한은 의도적으로 없다**(2026-08-07 재경님 «빼자» — 이식 원본인 디스코드 장치가 멘션 통과+허용목록 2겹뿐이고, 상한 6 을 잠깐 넣었다가 «정상 봇 회의 실측 11왕복»을 자르는 것이 확인돼 제거. 종료는 봇 규율 소관, 코드는 지목 없인 안 닿게만 한다). ⚠️ **게이트 순서 함정**(루돌프 라이브 실측): 구판은 사람 발신자 게이트가 봇 게이트보다 먼저라, `bot_id` 줄만 완화하면 봇 메시지(자기 U… 를 실음)가 사람 검사에서 먼저 죽어 **아무것도 안 열린다** — 그래서 한 분기로 접었다. id 축은 **U… 단일**(멘션 텍스트·사람 게이트와 같은 공간 — B…/U… 혼용이 낳은 태그 오독 재발 차단).
- **대상 게이트 — 채널에서는 «이 봇을 멘션한 글»만 처리**(2026-08-06 결함 13 수리): 기동 시 `auth.test` 로 자기 봇 user id 를 1회 확보하고(실패 = fail-fast 종료), 채널 인바운드는 본문에 `<@봇ID>` 가 있어야 통과. 예외 셋 — ①DM(`channel_type === 'im'`)은 1:1 이라 발신자 게이트로 충분 ②승인 답장(`yes/no <id>`, VERDICT_PATTERN)은 멘션 없이 오는 게 설계라 우회 ③**이 봇이 참여한 스레드의 «멘션 없는» 후속 발화**(`activeThreads` — 결함 17 상호작용 해소 + T4 정제: 스레드 안이라도 명시 멘션(`<@U…>/<@W…>`)이 등장하면 명시 지목이 이긴다 — 다른 봇만 불리면 침묵, 2026-08-06). 이 게이트가 없으면 `message.channels` 구독 탓에 **같은 채널에 이 브리지 봇이 N개면 N개 전원이 모든 글에 답한다**(2026-08-06 라이브 3중창 실측).
- **중복 방지**: `message`와 `app_mention`이 같은 포스트에 둘 다 발화할 수 있어 `ts`(최대 200개 evict 윈도)로 dedup.
- **스레드 = 대화 종류로 분기**(2026-08-06 결함 17 — 재경님 지시 "채널에서 태그하면 스레드 답글로"): **채널 인바운드는 항상 스레드**(top-level 이면 그 메시지 `event.ts` 를 루트로 합성 — 채널이 봇 답변으로 도배되지 않게) / **DM 은 사용자가 스레드를 연 경우에만**(1:1 에서 강제 댓글은 어색 — 구 주석의 근거를 DM 범위로 한정 유지). 그리고 **봇이 참여한 스레드의 후속 발화는 멘션 없이 통과**한다(대상 게이트의 스레드 면제 — `activeThreads`, 이 봇이 받은 스레드 루트만 기억하므로 다봇 채널에서 결함 13 이 스레드 안에서 부활하지 않는다).

## 권한 relay (opt-in)

`mcp.ts`가 `claude/channel/permission` capability를 선언하면(`mcp.ts:37-44`), Claude Code가 도구 실행 승인이 필요할 때 이 브리지를 통해 Slack으로 승인을 물을 수 있다. `server.ts`가 그 요청을 `Claude wants to run <tool>: <description>` 형식으로 최근 인바운드 채널에 posting하고(`server.ts:204-216`), 사용자가 `yes <5자리id>` / `no <5자리id>`로 답하면 그 verdict를 연결된 모든 세션에 broadcast한다(`server.ts:52,377-386` — 패턴은 5자리 id, 대소문자 무관, alphabet에서 `l` 제외는 Claude Code 자신이 관리). 허용 봇은 이 경로를 못 쓴다 — 봇 경로는 멘션 필수인데 VERDICT_PATTERN 은 anchored 라 멘션을 담을 수 없다.

⚠️ **이 기능을 declare하려면 발신자 게이트가 이미 있어야 한다** — `mcp.ts:38-43` 주석: "누구든 채널로 답할 수 있는 사람은 도구 승인/거부도 할 수 있다"는 게 채널 프로토콜 계약이라, 그 게이트 없이 이 capability만 선언하면 안 된다.

## 보안 모델 (README.md "Security model" 정리)

| 항목 | 내용 |
|---|---|
| 발신자 게이트 | `handleSlackEvent` 한 곳에서만 검사, 저자 종류로 분기 — 사람 = `ALLOWED_SLACK_USER_ID` 하나(메시지/@멘션/승인답장 전부 같은 체크포인트) / 봇 = `ALLOWED_SLACK_BOT_USER_IDS` 목록(U… 축) + 멘션 필수 + DM 금지. 왕복 상한 없음(디스코드 장치 원형 그대로 — 2026-08-07). 목록 미설정 = 봇 전면 차단(이식 전과 동일) |
| 채널 하드닝 | `event.channel === SLACK_CHANNEL_ID` OR DM. 원 레퍼런스 브리지(purujitgoyal)는 채널 검사가 아예 없어서, 봇이 다른 채널에 초대되면 허용된 사용자의 그 채널 발화까지 다 forward되는 갭이 있었다 — 여기선 막혀 있다 |
| Unix 소켓 | mode `0600`(listen() 성공 직후 chmod, `await` 사이 텀 없음) + peer UID 검증(`peercred.ts` `verifyPeerIsSelf` — macOS `getpeereid(3)`을 koffi로 호출, 접속 프로세스의 effective UID가 이 프로세스 자신과 다르면 거부) |
| 토큰 취급 | 실제 토큰은 레포 밖 `~/.claude/channels/slack/.env`에만 존재. 코드베이스 어디도 토큰 값을 로그/echo하지 않음 |
| 플랫폼 | peer-UID 체크는 **macOS**(`getpeereid`, koffi)와 **Linux/WSL**(`SO_PEERCRED` via `getsockopt`, 2026-08-06 추가, koffi — x86_64·arm64) 두 독립 경로로 지원한다. Linux/WSL 경로는 타입체크·빌드·구조체 정합까지는 확인했고, **실제 워크스페이스 왕복(WSL 실기)은 아직 검증되지 않았다.** 두 경로가 다 안 걸리는 환경(예: 순정 Windows 네이티브, `libc.so.6`/`libc.so` 로드 실패)에서는 README.md 원칙 그대로 조용히 스킵이 아니라 **모든 연결을 거부(fail closed)**한다 — 이 계약은 수리 전후 동일하다 |

## 여러 세션 동시 연결

여러 Claude Code 세션이 각자 `mcp.ts`를 띄워 같은 `server.ts`에 붙을 수 있다 — `server.ts`는 인바운드를 연결된 **모든** 클라이언트에 broadcast한다(`broadcast()` L80-85). 어느 세션이 "그" 대화를 담당하는지는 이 브리지가 정하지 않는다.

## Discord 쪽 (반자동 — API로 앱 생성 불가)

Discord는 앱 생성·봇 토큰 발급 API가 없다. 자동화 가능한 건 초대(OAuth2 URL)뿐:

1. https://discord.com/developers/applications → New Application → Bot 탭 → 토큰 발급 (수동)
2. 이후 봇 구동·페르소나·상태 관리는 `/thiscode:create-bot` 온보딩(`skills/create-bot/SKILL.md`)이 담당.

## 함정 목록 (재작성판 — DM 오기재 제거 + 신아키텍처 실측 반영)

| 함정 | 증상 | 처방 |
|---|---|---|
| `channelsEnabled` 조직 정책이 꺼져 있음 | `--dangerously-load-development-channels`를 줘도 채널이 안 뜸 | Console/API-key는 기본 켜짐. claude.ai Team/Enterprise는 Owner가 켜야 함 |
| 이미 뜬 인스턴스가 있는데 `npm start` 재실행 | 즉시 에러(싱글톤 가드) | 기존 프로세스를 먼저 내리거나, 진짜 죽은 게 확실하면 pidfile 제거 후 재시도 |
| `.env` mode가 0600이 아님 | 에러 없이 경고 로그만(계속 실행됨) | `chmod 600 "$STATE_DIR/.env"` (기본 `~/.claude/channels/slack/.env`) |
| Slack 이벤트 구독에 `message.im` 없이 DM 기대 | DM을 보내도 Slack이 애초에 이벤트를 안 줌(브리지 코드는 정상) | 앱 설정에서 `message.im` 이벤트 구독 추가(위 매니페스트 예시 참고) |
| Linux/WSL에서 이 브리지를 씀 | (2026-08-06 이전엔 모든 IPC 연결이 조용히 거부됐다) 지금은 `SO_PEERCRED` 경로로 정상 지원 대상이다 — 단 실제 워크스페이스 왕복은 **미검증**(코드 정합성까지만 확인, 런타임 미실행, README.md "Platform support") | 그래도 안 되면 `libc.so.6`(glibc) 로드가 되는지부터 확인 — 로드 자체가 실패하면 여전히 fail closed로 거부된다 |
| `--dangerously-load-development-channels`의 1회 확인 다이얼로그를 놓침 | 세션이 채널을 안 받는 것처럼 보임 | 첫 기동 시 다이얼로그에서 승인 필요(관문 E) |

> ⚠️ 위 함정 표는 소스 코드 실측(`server.ts`/`config.ts`/`singleton.ts`/README.md) 기반이며, 살아있는 Slack 워크스페이스에서의 왕복 재현은 이 문서 작성 시점까지 완료되지 않았다 — 실제 `npm start`→왕복까지는 이 스킬을 실행하는 환경에서 아래 검증 단계로 직접 확인한다.
