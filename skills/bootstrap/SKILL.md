---
name: bootstrap
description: Use when setting up a fresh Claude Code environment with Discord bot integration on WSL/Linux/macOS. Guides the user through environment detection, package installation, tmux setup with oh-my-tmux, Claude Code installation, and first bot wizard initialization.
license: MIT
compatibility: WSL Ubuntu 20.04+ / Linux native (Debian, Ubuntu, Fedora, Arch) / macOS (tmux >= 2.6 required)
metadata:
  author: treylom
  version: "0.1.0"
  hermes:
    tags: [Setup, Discord, Coding]
    requires_tools: [bash]
---

# thiscode bootstrap

> **사용 시점**: 새 머신에 Claude Code + Discord 봇 통합 환경을 처음 세팅할 때.

본 skill 은 `install.sh` 8-step 자동화 + 첫 봇 wizard 진입을 안내합니다. agent 가 사용자의 OS·환경을 인식하고 단계별로 명령을 제시합니다.

---

## 무엇을 하는 skill 인가

1. **환경 인식** — `uname` + `/proc/version` + 패키지 매니저 자동 detect
2. **install.sh 실행** — 8-step 자동화 (tmux + nvm + Node.js LTS + Claude Code + oh-my-tmux)
3. **Claude Code 인증** — `claude auth login` 브라우저 OAuth
4. **첫 봇 wizard 시동** — 추후 `/thiscode:start` 슬래시 커맨드 (v0.2)

---

## 단계별 안내

### Step A. 환경 점검 (사용자 input 0회)

```bash
uname -s                     # 🐧 👤 → "Linux" 또는 "Darwin"
grep -i microsoft /proc/version 2>/dev/null && echo "WSL 감지"
command -v tmux git curl     # 기본 도구 확인
```

agent 는 위 출력으로 OS / WSL / 패키지 매니저를 자동 판단합니다.

### Step B. install.sh 실행 (사용자 input 1회)

다음 명령을 사용자에게 제시:

```bash
curl -fsSL https://raw.githubusercontent.com/treylom/ThisCode/main/install.sh | bash
```

또는 git clone 후 로컬 실행:

```bash
git clone https://github.com/treylom/ThisCode.git ~/code/thiscode
cd ~/code/thiscode && bash install.sh
```

install.sh 가 자동으로 다음 진행:
1. 환경 detect (WSL / Linux / macOS)
2. 필수 패키지 (tmux + git + curl + jq + build-essential)
3. nvm + Node.js LTS
4. Claude Code 전역 설치
5. oh-my-tmux (`gpakosz/.tmux`) 자동 install
6. (선택) `thiscode` 의 `tmux.conf.local` 적용 — user confirm 후 백업 자동
7. Claude Code plugin install 안내
8. 첫 봇 wizard 안내

### Step C. Claude Code 인증

```bash
claude auth login                          # 🐧 👤 → 브라우저 인증
claude --version                           # 검증 → "2.x.x" 출력
```

### Step D. 첫 봇 wizard 진입

```bash
tmux new-session -s claude                 # 🐧 👤
cd ~/<project> && claude                   # 🐧 🤖
```

Claude Code 안에서:

```
/thiscode:start                       # 🤖 wizard 진입 (v0.2 에 신설 예정)
```

wizard 가 단계별 안내:
- Discord 봇 생성 (Developer Portal 이동)
- 봇 토큰 입력
- 첫 봇 페르소나 결정 (soul.md template)
- 페어링 + 첫 대화 검증

---

## 커맨드 범례

| 아이콘 | 의미 |
|---|---|
| 🐧 | WSL Ubuntu / Linux 터미널 |
| 🤖 | Claude Code 가 자동 실행 |
| 👤 | 사용자가 직접 입력 |
| ✅ | 성공 |
| ❌→✅ | 실패 후 수정 |

---

## 트러블슈팅

| 증상 | 대응 |
|---|---|
| `nvm: command not found` | 새 터미널 완전히 닫고 다시 열기 (`source ~/.bashrc` 안 될 수 있음) |
| `permission denied` on `install.sh` | `chmod +x install.sh` 또는 `bash install.sh` |
| tmux 중첩 오류 | 이미 tmux 안 → `Ctrl+B → c` 새 window |
| `claude auth login` 브라우저 안 열림 | 출력된 URL 을 수동으로 브라우저에 붙여넣기 |
| Discord 봇 페어링 코드 만료 | 봇에 다시 DM → 새 코드 |

---

## 추가 참고

- 상세 README: [../../README.md](../../README.md)
- install.sh 본문: [../../install.sh](../../install.sh)
- tmux.conf.local: [../../configs/tmux.conf.local](../../configs/tmux.conf.local)
- 한국어 docs: [../../docs/](../../docs/)
- gpakosz/.tmux 원본: https://github.com/gpakosz/.tmux
- agentskills.io 표준: https://agentskills.io/specification

---

## 호환성 정보

본 SKILL.md 는 **agentskills.io 표준** 을 따릅니다 (`name` + `description` core 2 키). 따라서 다음 agent 런타임에서 cross-tool 호환:

| Agent | 인식 |
|---|---|
| Claude Code | ✅ primary |
| Hermes Agent (NousResearch) | ✅ `metadata.hermes` 확장 인식 |
| Codex CLI / Cursor / Gemini CLI / Goose / OpenCode 등 | ✅ core frontmatter 호환 |

확장 필드 (`metadata.hermes.tags`, `compatibility`)는 추가됐을 때 본 도구에서 활용, 다른 표준 client 에선 자동 무시 (forward-compatible).

---

## How to Use This Skill

Use this skill during initial setup to guide environment detection and automated installation. It handles package installation, tmux configuration, Claude Code authentication, and prepares your system for bot operations.
