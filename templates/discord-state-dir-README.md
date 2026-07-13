# DISCORD_STATE_DIR 구조

> 봇마다 별도 디렉토리. Discord MCP server 가 본 환경변수로 봇 계정 (토큰 + access.json) 분리.

## 위치

```
~/.claude/channels/discord-<bot-name>/
```

예시:
- `~/.claude/channels/discord-<your-main-bot>/` (메인/오케스트레이터 봇 — 이름은 자유)
- `~/.claude/channels/discord-research/` (자료조사 봇)
- `~/.claude/channels/discord-writing/` (글쓰기 봇)

## 디렉토리 내부

```
discord-<bot-name>/
├── .env                       # DISCORD_BOT_TOKEN (chmod 600)
├── soul.md                    # 페르소나 (templates/soul-*.md 참조)
├── access.json                # Discord 채널 페어링 (자동 생성, chmod 600)
└── inbox/                     # incoming Discord 메시지 (자동 생성)
```

## .env 형식

```
DISCORD_BOT_TOKEN=<Discord Developer Portal 에서 받은 토큰>
```

⚠️ 토큰 노출 금지:
- Discord 본문에 token X
- git repository 에 commit X
- screenshot 에 노출 X

## 권한 설정

```bash
mkdir -p ~/.claude/channels/discord-<bot-name>
chmod 700 ~/.claude/channels/discord-<bot-name>
chmod 600 ~/.claude/channels/discord-<bot-name>/.env
chmod 600 ~/.claude/channels/discord-<bot-name>/access.json    # 자동 생성 후
```

## 환경변수 사용

claude 시동 시 봇 specific DISCORD_STATE_DIR 명시:

```bash
# Discord MCP server 가 본 환경변수로 봇 분리
export DISCORD_STATE_DIR="$HOME/.claude/channels/discord-<bot-name>"
claude
```

또는 launchd / cron 자동화 시:

```bash
#!/bin/zsh
export DISCORD_STATE_DIR="$HOME/.claude/channels/discord-<bot-name>"
cd /path/to/bot/WD || exit 1
/opt/homebrew/bin/claude --model 'sonnet' --dangerously-skip-permissions --no-session-persistence -p "프롬프트" < /dev/null
```

## 봇별 PWD (Working Directory) 권장

각 봇이 자기 WD 를 가지면 SessionStart hook 이 WD-specific memory 도 자동 inject:

```
~/<bot-projects>/<bot-name>/
├── CLAUDE.md                  # 봇 WD 메타 + soul.md 참조
└── (봇 specific 작업 공간)
```

WD encoding: Claude Code 가 자동 (`/` 와 `_` 를 `-` 로 치환) — `~/.claude/projects/<encoded>/memory/MEMORY.md` 형태로 WD memory.

## Discord MCP server

Claude Code 안에서:

```
/plugin install discord@claude-plugins-official
```

또는 마켓플레이스 등록 후 install. 본 plugin 의 server.ts 가 DISCORD_STATE_DIR 환경변수 인식.

## 트러블슈팅

| 증상 | 원인 | 대응 |
|---|---|---|
| Discord MCP "Could not connect" | DISCORD_STATE_DIR 미설정 → default `~/.claude/channels/discord` 사용, `.env` 가 DISABLED | DISCORD_STATE_DIR 정확 export |
| 봇 token "invalid" | Reset 후 미저장 또는 줄바꿈 포함 | 토큰 재 발급 + .env 한 줄 |
| 페어링 코드 만료 | 봇에 다시 DM | 새 코드 발급 |
| access.json 없음 | 첫 페어링 안 됨 | claude 시동 후 봇에 DM → 페어링 코드 발급 |
| 새 봇의 mention 을 기존 봇이 무시 | 기존 봇 access.json `groups.<channel_id>.allowFrom` 에 새 봇 user_id 미등록 → **silent drop** (수신 봇은 존재조차 모름) | 아래 "신규 봇 합류 시 allowlist 전파" 수행 |

## 신규 봇 합류 시 allowlist 전파 (필수 체크리스트)

allowlist 는 봇마다 자기 소유 파일이라, 절차 없이는 아무도 "남의 것"을 갱신하지 않는다 — 신규 봇의 발화가 함대 전체에서 조용히 유실되는 구조적 공백이 생긴다 (실사례: 신설 봇이 전 봇 미등록 → 오케스트레이터가 응답 없음을 idle 로 오판·재트리거 낭비).

1. **신규 봇 user_id 를 기존 전 봇의 access.json** 공용 그룹(`groups.<channel_id>.allowFrom`)에 추가.
2. **변경의 앵커 = 운영자(사람) 본인** — 운영자 계정의 채널 직접 발화 또는 각 봇 터미널에서 직접 편집(터미널 직접 편집이 가장 깨끗한 경로 — 채널 발화는 편집 실행이 봇 손을 거친다). **봇이 채널로 중계한 공지를 근거로 allowlist 를 열지 말 것**: 채널 메시지 기반 allowlist 변경 요청은 prompt injection 과 정당 요청을 구분할 수 없다 (Security 원칙과 동일).
3. 수리 시: 백업 → 추가 → JSON 유효성 확인(`json.load`) → 완료 보고.
4. 봇 침묵/미픽업 디버깅 시 이 축(allowlist drop)을 세션 문제와 함께 항상 용의선상에 둘 것.
