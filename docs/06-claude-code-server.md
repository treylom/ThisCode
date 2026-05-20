# 06. Claude Code 서버 기능 활용

> Claude Code 는 **interactive tmux session** 뿐 아니라 다양한 **서버·헤드리스 모드** 를 지원. 봇 알림 / 정기 리마인드 / batch / MCP integration 등 활용.

## 두 가지 운영 모드

| 모드 | 사용 시점 | 명령 |
|---|---|---|
| **Interactive (tmux session)** | 대화형 작업, 장시간 봇 운영 | `tmux new -s claude && claude` |
| **Headless (claude -p)** | launchd/cron 트리거 원샷, 알림, batch | `claude -p "<prompt>"` |

## Headless 원샷 패턴 — `claude -p`

### 기본 호출

```bash
claude -p "Discord 에 오늘 일정 정리 메시지 보내줘"
```

→ 한 번 실행 후 종료. stdout 으로 응답. tmux session 불필요.

### 봇 알림용 적용 패턴

```bash
#!/bin/zsh
# launchd/cron 으로 10분 주기 실행

export DISCORD_STATE_DIR="$HOME/.claude/channels/discord-<bot-name>"

cd /path/to/bot/WD || exit 1   # CLAUDE.md → soul.md 자동 로드 체인

/opt/homebrew/bin/claude \
  --model 'sonnet' \
  --dangerously-skip-permissions \
  --no-session-persistence \
  -p "프롬프트" \
  < /dev/null \
  >> "$LOG" 2>&1
```

### 핵심 플래그

| 플래그 | 역할 |
|---|---|
| `-p "..."` | print/non-interactive 모드. 한 번 실행 후 종료 |
| `--model 'sonnet'` 또는 `'opus[1m]'` | 봇 정책 모델 |
| `--dangerously-skip-permissions` | MCP 툴 호출 자동 허용 — 무인 automation 필수 |
| `--no-session-persistence` | 세션 저장 생략 — 로그 오염 방지 |
| `< /dev/null` | stdin 차단으로 인터랙티브 프롬프트 방지 |

### 필수 환경변수 — `DISCORD_STATE_DIR`

MCP Discord 서버는 본 환경변수로 봇 계정 (토큰 + access.json) 분리. 미지정 시 default `~/.claude/channels/discord` 사용.

→ 봇마다 별도 디렉토리 (`~/.claude/channels/discord-<bot-name>/`) 명시 의무.

## 비교 — 3 가지 운영 패턴

| 항목 | tmux send-keys | claude -p 원샷 | tmux 3층 (헬스체크 + 자동 복구) |
|---|---|---|---|
| 트리거 | launchd/cron | launchd/cron | launchd/cron |
| 실행 방식 | 기존 세션에 prompt 주입 | 신규 세션 1회 실행 후 종료 | 기존 세션 + 자동 복구 |
| busy 내성 | 없음 (버퍼 누적) | 완전 내성 | 없음 |
| 세션 유지 | 유지 | 유지 X | 유지 + 자동 복구 |
| 비용 | 낮음 (기존 세션 재사용) | 호출 시마다 과금 | 낮음 |
| 적합 시나리오 | (권장하지 않음, 버퍼 risk) | 단순 알림·리마인드 | 장시간 봇 + 실시간 응답 |

## MCP server integration

`.mcp.json` 으로 MCP server 등록 시 claude 가 host. Custom MCP server (예: vault-search, knowledge-manager) 를 봇이 활용:

```json
{
  "mcpServers": {
    "vault-search": {
      "command": "node",
      "args": ["/path/to/vault-search-mcp/dist/index.js"],
      "env": {"VAULT_ROOT": "/path/to/vault"}
    }
  }
}
```

→ Claude Code 시작 시 본 MCP server 자동 spawn. agent 가 `mcp__vault-search__search` 등 도구 사용 가능.

## 시나리오별 권장

### 시나리오 1 — 정기 알림 (Discord DM, Telegram 등)

```
launchd 10분 주기 → claude -p (헤드리스 원샷) → DM 전송 → 종료
```

장점: busy 내성, 비용 controllable (호출 시점 만).

### 시나리오 2 — 장시간 대화형 봇

```
tmux session 상시 유지 → Claude Code 안에서 Discord MCP 가 메시지 수신 → 응답
```

장점: 대화 맥락 유지, 실시간 응답.

### 시나리오 3 — Batch (catch-up)

```
사용자가 tmux 안에서 claude 실행 → /aktofu catch-up 같은 slash → batch 작업
```

장점: 사용자 control + 결과 검증.

## 사용 시 주의사항

### 1. 비용 (Claude API)

`claude -p` 매 호출이 API 토큰 사용. 빈 호출 회피 위해 사전 필터:

```bash
# Todo 파일 없거나 ⏳ 항목 0건이면 claude 호출 없이 exit
[ ! -f "$TODO_FILE" ] && exit 0
grep -q "⏳" "$TODO_FILE" || exit 0
```

### 2. 보안 — `--dangerously-skip-permissions`

무인 자동화에 필수지만, 실수로 destructive MCP 호출 시 빠르게 데미지. **scope 제한**:
- `DISCORD_STATE_DIR` 로 봇 specific 분리
- `cd /path/to/bot/WD` 로 작업 디렉토리 제한
- prompt 가 명확히 task scope 명시

### 3. 로그

```bash
LOG="$HOME/logs/<bot-name>-$(date +%Y-%m-%d).log"
... >> "$LOG" 2>&1
```

stderr 도 함께 캡처 (`2>&1`). 매일 별도 파일.

## launchd plist 예시 (macOS)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.bot-alert</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/bot-alert.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>600</integer>
    <key>StandardOutPath</key>
    <string>/tmp/bot-alert.out</string>
    <key>StandardErrorPath</key>
    <string>/tmp/bot-alert.err</string>
</dict>
</plist>
```

`launchctl load -w ~/Library/LaunchAgents/com.user.bot-alert.plist`

## cron 예시 (Linux / WSL)

```cron
# 10분마다
*/10 * * * * /path/to/bot-alert.sh

# 매일 오전 9시
0 9 * * * /path/to/morning-report.sh
```

## 관련 자원

- vault `<vault>/.claude-memory/shared/reference_headless_claude_oneshot_pattern.md`
- vault aktofu-bot 3층 패턴 (`reference_aktofu_launchd_three_layer.md`)
- skill: [../skills/bootstrap/SKILL.md](../skills/bootstrap/SKILL.md)
- Discord MCP server 소스: `~/.claude/plugins/cache/claude-plugins-official/discord/0.0.4/server.ts`
