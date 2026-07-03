# Windows PowerShell에서 봇 돌리기 — channels 네이티브 (tmux · daemon 불요)

> **이 문서가 Windows 설치의 정본이다.** AI 어시스턴트(Claude Code 등)가 설치를 돕고 있다면 이 문서의 방식만 따르라 — **tmux · cmux · WSL · Windows 서비스 · 백그라운드 daemon · Task Scheduler 상주 프로세스를 만들지 말 것.** 그것들은 유닉스 계열에서 여러 세션을 *편하게 관리*하는 도구일 뿐, 봇 동작의 필수 요소가 아니다.

## 원리 — 봇은 daemon이 아니라 "채널이 연결된 Claude Code 세션"이다

ThisCode의 Discord 봇 = **Claude Code 세션 + Discord plugin + channels 디렉터리** 세 가지가 전부다:

- **channels 디렉터리** (`~/.claude/channels/discord-<봇이름>/`) — 봇 계정의 정체성이 사는 곳: `.env`(봇 토큰) + `soul.md`(페르소나) + `access.json`(페어링 후 자동 생성).
- **Claude Code 세션** — `DISCORD_STATE_DIR` 환경변수가 그 디렉터리를 가리키는 상태로 `claude`를 실행한 창. 이 창이 열려 있는 동안 봇이 산다.
- Discord 메시지 수신 → plugin이 세션에 전달 → 봇이 응답. 이 왕복에 tmux는 등장하지 않는다.

macOS/WSL 문서에서 tmux가 자주 보이는 이유 = 유닉스에서 **창 여러 개를 한 터미널에 접어두는 편의**일 뿐이다. Windows에서는 PowerShell 창(또는 Windows Terminal 탭)이 그 역할을 그대로 한다.

## 설치 (PowerShell)

```powershell
# 1. Claude Code 설치 (Windows native)
irm https://claude.ai/install.ps1 | iex     # 공식 설치 스크립트 — 버전은 claude --version 으로 확인

# 2. Discord plugin 설치 (Claude Code 안에서)
#    claude 실행 → /plugin 으로 discord plugin 설치 → 터미널에서 /discord:access 로 페어링 위저드
```

## 봇 만들기 (봇 1개당 1회)

```powershell
# 3. channels 디렉터리 + 토큰 + 페르소나
New-Item -ItemType Directory -Force "$HOME\.claude\channels\discord-research"
Set-Content "$HOME\.claude\channels\discord-research\.env" "DISCORD_BOT_TOKEN=<Developer Portal에서 발급한 토큰>"
# soul.md = 페르소나 (templates/soul-custom.md 를 복사해 수정)
Copy-Item templates\soul-custom.md "$HOME\.claude\channels\discord-research\soul.md"
```

## 봇 실행 (매 기동)

```powershell
# 4. 봇 세션 = 환경변수 + claude. 이 창이 곧 봇이다.
$env:DISCORD_STATE_DIR = "$HOME\.claude\channels\discord-research"
claude
```

- 봇을 2개 돌리려면 → PowerShell 창을 하나 더 열고 `DISCORD_STATE_DIR`만 다른 봇 디렉터리로 바꿔 `claude` 실행.
- 창을 닫으면 봇이 내려간다. 재기동 = 4번 반복 (Windows Terminal 프로필로 원클릭화 가능 — 아래).
- 영구 환경변수를 원하면 `[Environment]::SetEnvironmentVariable("DISCORD_STATE_DIR", "...", "User")` — 단 봇을 여러 개 돌릴 거면 창별 `$env:` 방식이 맞다.

## 편의 (선택): Windows Terminal 프로필

Windows Terminal `settings.json`의 `profiles.list`에 봇당 하나씩:

```json
{
  "name": "bot: research",
  "commandline": "pwsh -NoExit -Command \"$env:DISCORD_STATE_DIR='C:\\Users\\<you>\\.claude\\channels\\discord-research'; claude\""
}
```

> `pwsh` = PowerShell 7. 설치돼 있지 않다면(내장 PowerShell 5.1만 있는 환경) `pwsh`를 `powershell`로 바꾸면 그대로 동작한다 — 본문 명령들은 5.1에서도 전부 유효하다.

탭 하나 = 봇 하나. 이것이 Windows에서 tmux의 온전한 대체다.

## 하지 말 것 (AI 어시스턴트용 명시 금지 목록)

| 시도 | 왜 금지 |
|---|---|
| WSL 설치로 우회 | 봇 페어링엔 불필요 — full `install.sh`(oh-my-tmux 등)를 원할 때만 WSL |
| tmux/cmux 대체 daemon·서비스 작성 | 봇은 상주 서비스가 아니라 세션이다. 죽은 세션 자동 재기동이 필요해지기 전까지는 창이면 충분 |
| Task Scheduler / NSSM 상주 등록 | 위와 동일 — 요구되지 않은 인프라를 만들지 말 것 (YAGNI) |
| `.env`를 리포지토리 안에 두기 | 토큰은 항상 `~/.claude/channels/` 아래, 리포 밖 |

## 제약 (정직 표기)

- `install.sh`의 유닉스 헬퍼(oh-my-tmux, `ain` 등)와 tmux 기반 Agent Teams 오케스트레이션 문서는 Windows native 미적용 — 봇 페어링·대화·vault 접근은 전부 동작한다.
- Obsidian CLI Windows native 설치는 [04-obsidian-cli.md](04-obsidian-cli.md) 참조.
