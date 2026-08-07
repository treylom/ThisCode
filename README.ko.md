![ThisCode — Tofu](assets/readme-banner.png)

# ThisCode

> Claude Code + Discord 봇 + codex 호출 통합 플러그인 — 개인 vault 자동화 + 멀티에이전트 운영
>
> **역할 경계**: ThisCode = 봇 하네스 운영 번들(운영 규칙·GraphRAG 운영 vendor·배포 계약). 범용 지식관리 제품은 [knowledge-manager](https://github.com/treylom/knowledge-manager), 플러그인 설치 창구는 [tofukyung-plugins](https://github.com/treylom/tofukyung-plugins)가 정본입니다.
>
> 🌐 **English version**: [README.md](README.md) · 📘 **Setup**: [docs/SETUP.md](docs/SETUP.md) (개발자) · 🌱 [docs/SETUP-BEGINNER.md](docs/SETUP-BEGINNER.md) (초보자) · 🧩 [docs/AGENTS.md](docs/AGENTS.md) (Custom Hybrid v1.0) · ⚙️ **[설정 가이드](docs/SETUP-CONFIG-GUIDE.md)** (CLAUDE.md · soul.md · rules · Skills 2.0) · 🆕 **[최근 변경](docs/RECENT-CHANGES.md)** (설치 시 읽기 — AI가 자동 반영할 최신 변경 요약) · 📖 **[시작 안내서 (한국어 PDF)](docs/getting-started/ThisCode-ThisCodex-getting-started.pdf)** (초보자, 14p) · 📄 **[전체 정리 한 장 (HTML)](docs/SUMMARY.html)** · 🤝 **[ThisCodex](https://github.com/treylom/ThisCodex)** (Codex 동반 런타임)

## AI에게 설치 맡기기

Claude Code 또는 Codex에 그대로 붙여 넣으세요:

```text
https://github.com/treylom/ThisCode 에 있는 설치 파일을 따라 단계별로 설치해줘. README.md부터 읽고, 안내형 설정을 진행하고, 토큰/자격증명이나 시스템 패키지를 건드리기 전에는 나에게 확인하고, 마지막에 문서의 검증 명령까지 실행해줘.
```

![ThisCode 핵심 그림 — 구조화된 옵시디언 볼트, 작업 디렉토리별 적합한 봇, 디스코드로 운영, 봇끼리 협업](assets/core-mental-model.png)

> **처음 오셨나요?** 핵심은 — **구조화된 옵시디언 볼트**를 두고, **각 작업 디렉토리에 적합한 봇**을 배치해, **디스코드**로 그 봇들을 쓰고 **봇끼리 협업**하게 하는 것입니다. 공유 메모리·검색은 부가 효과지 핵심이 아닙니다. 사전 지식 없이 위 Setup 링크부터 따라오시면 됩니다.

![ThisCode + ThisCodex 상세 배선 (tmux · app-server · 디스코드 · 볼트)](assets/architecture.png)

WSL / Linux / macOS 어디서든 `bash install.sh` 한 줄로 Claude Code + tmux 환경을 세팅합니다. **핵심 가치**: *구조화된 옵시디언 볼트* 안에서 *각 작업 디렉토리에 적합한 봇*을 두고, *디스코드*로 쓰며, *봇끼리 협업*하게 하는 것. 4-Tier 볼트 검색(GraphRAG → vault-search MCP → Obsidian CLI → ripgrep) + LLM 모델 라우팅은 그 봇들을 쓸모 있게 만드는 보조 기능이지 핵심이 아닙니다.

> **시작 전 권고:** (1) 옵시디언 **폴더 구조**부터 잡으세요; (2) 메모리·내부검색을 제대로 쓰려면 **옵시디언 설치** 권장. **옵시디언 없이?** 단순 연결용 디스코드 봇만 띄울 수도 있지만, 그 경우 볼트 메모리·내부 검색 품질은 **보장되지 않습니다**.

## 🛠️ Zero-config 설치

**Prerequisite:** Claude Code CLI 이미 install + auth 의무 (https://claude.ai/code). `install.sh` 의 `install-superpowers.sh` step 안 `claude` CLI 호출.

wizard 안 거치고 **single command 으로 install** 원하는 learner 용:

```bash
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode
cd ~/.claude/plugins/thiscode
bash scripts/install.sh --apply
```

본 single command 안 install 되는 5 dep:

1. **superpowers** plugin (Claude Code plugin manager 호출)
2. **ripgrep** (Tier 4 baseline — brew / apt / dnf / apk 다 pkg manager fallback)
3. **Obsidian CLI** detect (Tier 3 — 미설치 시 manual download 안내)
4. **GraphRAG core** (Tier 1 — vendored Python runtime + 7-pkg pip install)
5. **Dense embedding** (옵션 4-channel — 사용자 confirm 1회, ~1GB)

Install 후: `bash scripts/healthcheck.sh` (6-phase 검증: superpowers + ripgrep + obsidian-cli + vault-search MCP + GraphRAG + Dense embedding).

**Windows 사용자:** WSL 2 (Ubuntu 22.04+) **required**. Native Windows (Cygwin / Git Bash / MSYS) 는 install.sh 안 detect 되며 WSL 사용 안내. PowerShell port = 후속 cycle 예정.

**Dependency provenance:** 19 entries 매트릭스 (Plugin 1 + Spec doc 2 + External tools 8 + Optional Dense 3 + Vendored Python runtime 1 + Vendored prompt skill 1 + Vendored Slack bridge 1 + Vendored vault-search MCP 1 + thiscode 1) [ATTRIBUTIONS.md](ATTRIBUTIONS.md) 안 명기. Cross-license compatibility Phase 1 GPT-5.5 review 검증 (MIT + Apache 2.0 + BSD-3 + Unlicense — 모두 permissive, copyleft zero) — Slack bridge 항목은 저작권자 결정으로 MIT 통일(2026-08-06), 본 repo와 동일.

## 🚀 Quickstart (vault-first)

```bash
# 1. thiscode 설치 (Claude Code plugin)
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode

# 2. wizard 진입 — env 자동 감지 + Phase 추천
bash ~/.claude/plugins/thiscode/scripts/claude-discode-init.sh

# 또는 Claude Code 안에서
/thiscode:init
```

wizard 가 vault 상태 / 도구 / 자원 detect 후 **8 Phase progressive journey** 추천:
- **Phase 1-2**: 즉시 (ripgrep + obsidian-cli)
- **Phase 3**: 100+ 노트 → vault-search MCP 권유
- **Phase 4**: 500+ 노트 권유 / 1000+ strong / 옵션 언제나 (GraphRAG)
- **Phase 5**: 2000+ 노트 → km-at Mode R preflight (read-only 진단)
- **Phase 6-7**: advanced (Dashboard / 하이브리드 4채널)

> **GraphRAG = 환경 감지 + 선택사항** (사용자 spec). 노트 수 미충족 시도 force install 가능.

## 💬 플러그인 커맨드 & 스킬 도움말

각 플러그인 커맨드와 스킬에는 내장 도움말이 있습니다:

### 플러그인 커맨드

Claude Code 내에서 `/thiscode:help` 를 실행하면 모든 사용 가능한 커맨드와 언제 사용하는지 확인할 수 있습니다:

- `/thiscode:start` — 초기 셋업 wizard (환경 인식, 봇 페어링, 검증)
- `/thiscode:init` — 경험자용 경량 셋업
- `/thiscode:create-bot` — 새 Discord 봇 생성 (soul.md 템플릿 포함)
- `/thiscode:create-slack-bot` — Discord 대신(또는 추가로) Slack에 봇 연결 (claude-channel-server 브리지 자동 셋업, 별칭: `/thiscode:slack-configure`)
- `/thiscode:km` — 지능형 variant 라우팅 knowledge manager (lite/at/plain)
- `/thiscode:search` — 4-tier vault 검색 (quick/deep 모드)
- `/thiscode:open-meeting` — 다봇 협업용 회의실 구조 생성
- `/thiscode:codex-check` — Codex CLI 브리지 연결 확인
- 그 외 다수 — `/thiscode:help` 로 전체 목록 확인

### 스킬

각 스킬 (bootstrap, knowledge-manager, search, meetings 등)의 SKILL.md 에는 **"How to Use This Skill"** 절이 있어 언제 호출하는지, 무엇을 하는지 설명합니다. vault 관련 스킬은 검색에, knowledge-manager 스킬은 콘텐츠 수집과 재정리에 초점을 맞추며 각 variant (lite/at/plain/full) 마다 기능 세트가 다릅니다.

---

## 선택: Discord 봇 + Agent Teams

본 플러그인의 Discord 봇 및 Agent Teams 통합은 선택사항입니다. vault-first 검색만으로도 완전히 작동하며, Discord 페어링 및 tmux 세션은 advanced use case 용입니다.

> **Slack을 쓰고 싶다면?** Discord 대신(또는 추가로) Slack으로도 봇을 페어링할 수 있습니다 — `/thiscode:create-slack-bot`(별칭: `/thiscode:slack-configure`) 실행 시 CLI 로그인·앱 설치 승인·토큰 입력 같은 사람 관문만 안내받고 나머지는 자동으로 처리됩니다. 상세: [skills/slack-configure/SKILL.md](skills/slack-configure/SKILL.md). 운영·트러블슈팅 참조: [skills/slack-bridge/SKILL.md](skills/slack-bridge/SKILL.md).

### Discord로 할 수 있는 것

봇을 한 번 페어링(연결)하면, Discord가 vault 봇들의 리모컨이 됩니다 — 터미널 없이도:

- **💬 멘션으로 작업 의뢰** — `@봇 오늘 노트 요약해줘` 하면 봇이 자기 세션에서 일하고 채널로 답해요.
- **🧵 스레드로 회의** — 스레드를 하나 열어 여러 봇이 협업. 각 봇이 공유 회의 문서를 같이 읽고 씁니다.
- **⏰ 잠든 봇 깨우기** — 조용해진 봇은 채널 메시지로 다시 깨웁니다 (신호는 항상 채널로 — 봇의 tmux에 입력을 직접 꽂는 건 금지, `rules/discord-comms.md` §5).
- **📎 파일·이미지 주고받기** — 스크린샷이나 문서를 첨부하면 봇이 받아서 작업해요.
- **🧹 세션 정리** — 사람(운영자)이 `/compact`·`/clear` 같은 세션 관리 명령을 봇 tmux 세션에 직접 보내 컨텍스트를 비울 수 있어요 (`rules/discord-comms.md` §5 R5).

> 여기 적은 건 일상적으로 자주 쓰는 동작이에요. 채널 모드로 세션을 더 정교하게 다루는 모델(Admin / Main / Session 라우팅)은 [`docs/connector-session-ux.md`](docs/connector-session-ux.md) 참고.

---

## 📊 4-Tier Search Benchmark

thiscode 의 4-Tier search 가 일반 `obsidian-cli` / `/search` / `/vault-search` 대비 어떤 trade-off 를 보이는지 5-axis 로 측정합니다. **본인 vault 에서 직접 측정** 하면 본인 환경의 실제 trade-off 가 보입니다.

```bash
# 본인 vault 로 측정 (Tier 1 GraphRAG 사용 시 server 별도 띄움 필요)
VAULT=~/path/to/your/vault bash benchmark/runners/run-all.sh
python3 benchmark/report-generator.py --print-only
```

수치는 vault 크기·컨텐츠·hardware 에 따라 크게 다릅니다 — v1.0 은 고정 벤치 수치 대신
러너와 측정 방법론을 동봉합니다. 위 스크립트를 본인 vault 에 돌려서 의미 있는 수치 확보.

> 측정 방법 + 해석 가이드 + 본인 vault fixture 작성: [docs/BENCHMARK.md](docs/BENCHMARK.md)
> CI 자동 측정 결과(sample fixture, Tier 4 ripgrep): [benchmark/results/](benchmark/results/)

---

## 🧠 LLM 모델 routing

thiscode 는 검색 결과 받은 후 응답 생성 시 task complexity 따라 모델을 자동 선택:

| Task | Claude 사용자 | GPT/[Codex](docs/GLOSSARY.md#codex) 사용자 |
|---|---|---|
| 단순 (factual lookup) | Haiku | gpt-5.5 |
| 중간 (요약 / 분류) | Sonnet | gpt-5.5-codex |
| 종합 (multi-doc 추론) | Opus[1m] | gpt-5.5-codex-spark |

`scripts/route-model.mjs` heuristic — query length / 키워드 기반. user override `--model haiku|sonnet|opus`.

**Tier 순서:** Tier 1 [GraphRAG](docs/SETUP.md#tier-1) → Tier 2 [vault-search MCP](docs/SETUP.md#tier-2) → Tier 3 [Obsidian CLI](docs/SETUP.md#tier-3) → Tier 4 [ripgrep](docs/SETUP.md#tier-4). 정확도 우선 fallback.

## 📚 용어 모르겠으면? → [GLOSSARY.md](docs/GLOSSARY.md)

30+ 용어 풀이 (LLM / MCP / CEL / embedding / recall@5 / kg_depth / fallback / dispatcher / 등).

---

## 🚀 빠른 시작 (3 step)

### Step 1. 환경 인식 + 자동 설치

```bash
curl -fsSL https://raw.githubusercontent.com/treylom/ThisCode/main/install.sh | bash
```

또는 git clone 후 로컬 실행:

```bash
git clone https://github.com/treylom/ThisCode.git ~/code/thiscode
cd ~/code/thiscode && bash install.sh
```

`install.sh` 가 10 step 자동 수행:

| 단계 | 작업 | 의존 |
|---|---|---|
| 1 | OS / Distro detect (WSL / Linux / macOS) | uname |
| 2 | 필수 패키지 (tmux + git + curl + jq + build-essential) | apt / dnf / yum / brew / pacman |
| 3 | nvm + Node.js LTS | curl |
| 4 | Claude Code 전역 설치 | npm |
| 4.5 | **Codex CLI** (`@openai/codex`) 전역 설치 — codex 호출 layer 의존 | npm |
| 5 | oh-my-tmux (`gpakosz/.tmux`) 자동 install | git |
| 6 | (선택) thiscode `tmux.conf.local` 적용 | user confirm |
| 6.5 | **Obsidian CLI** (Mac brew cask / WSL Windows native / Linux snap·flatpak·deb) — 3-Tier 폴백 1순위 | brew / snap / 수동 |
| 7 | Claude Code plugin install 안내 (marketplace 등록 + 슬래시 7종) | (Claude Code 안 슬래시) |
| 8 | 첫 봇 wizard 안내 (`/thiscode:start`) | (Claude Code 안 슬래시) |

플러그인 install 후 자동 인식되는 슬래시 7종:
- `/thiscode:start` — 메인 wizard (환경 인식 + 봇 셋업 + 첫 대화)
- `/thiscode:install-hooks` — SessionStart + UserPromptSubmit + **Stop(활성 회의 재독)** hook merge (~/.claude/settings.json 안전 병합, 기존 hook 보존). SessionStart 가 soul.md + 메모리 + `rules/INDEX.md` 주입, Stop 훅이 최근 규칙/회의 변경을 자동 반영하는 경로 — [docs/RECENT-CHANGES.md](docs/RECENT-CHANGES.md) 참조
- `/thiscode:create-bot` — 신규 봇 디렉토리 + .env + soul.md template 자동 셋업
- `/thiscode:create-discord-bot` — 추가 Discord 봇 1개 신설 (별칭: `/thiscode:add-bot`)
- `/thiscode:create-slack-bot` — Slack 워크스페이스 연결 (claude-channel-server 브리지 자동 셋업, 별칭: `/thiscode:slack-configure`)
- `/thiscode:open-meeting` — 회의실 폴더 신설 (다 봇 협업 4-file)
- `/thiscode:codex-check` — Codex CLI 검증 (호출 layer 활성 확인)
- `/thiscode:self-update` — 자가 업데이트 체크 (git fetch behind 비교)

순정 Claude Code 부트스트랩 (hook + 봇 없는 상태):

```
1. /thiscode:install-hooks   # SessionStart + UserPromptSubmit + Stop(회의 재독) hook 등록
2. /thiscode:create-bot      # 첫 봇 디렉토리 + soul.md 셋업
3. /thiscode:start           # 메인 wizard (Discord 페어링 + 첫 대화 검증)
4. /thiscode:codex-check     # Codex CLI 활성 확인 (선택)
```

## 📦 운영 노하우 가이드 (docs/)

thiscode 가 packaging 한 우리 vault 운영 노하우:

- [03-shared-memory.md](docs/03-shared-memory.md) — **공유 메모리 4-tier** (T1 git-tracked / T2 machine-specific / T3 project-meetings / T4 per-bot WD)
- [memory-dreaming.md](docs/memory-dreaming.md) — **메모리 정리(지우지 않고 옮김) 쉬운 설명**: 안 쓰는 메모리를 작업공간 밖 보관소로 *옮기고* 명령 한 줄로 *되돌립니다*(체크섬 검증). 9칸 전부 같은 기준표(Codex 포함)·보수적(자동이동 실측 0건·애매하면 사람검토)·기준은 자기 실수서 학습. 도구 `scripts/memory_dreaming.py`(`--scan` 기본 미리보기 / `--apply` 게이트 / `--restore`), 주1회 강제(YAML+세션시작 경고+launchd 3중)
- **orchestrator-watchdog** (`scripts/meeting_watchdog.py`) — **회의 진행 watchdog (회의마다 권장 — 감시 봇 1개 초대, 첫 dispatch 전에 가동)**: 회의 스레드 신설 시 ~5분마다 진행 점검(메인테이너 vault 는 ~3분 운영), 목표+전체 작업 완료 시에만 자동 종료(Claude `/goal` 응용). fail-closed = 살아있는 회의 절대 잘못 종료 안 함. [05-meeting-thread-protocol.md](docs/05-meeting-thread-protocol.md) §2.3 + [rules/meeting-protocol.md](rules/meeting-protocol.md) §5 와 짝
- [04-obsidian-cli.md](docs/04-obsidian-cli.md) — **Obsidian CLI 설정** (Mac brew / WSL Windows native / Linux snap·flatpak·deb) + 3-Tier 폴백 (CLI → MCP → Write/Read/Grep) + 알려진 버그·워크어라운드
- [06-claude-code-server.md](docs/06-claude-code-server.md) — **Claude Code 서버 기능** (`claude -p` 헤드리스 + MCP server + tmux session vs headless 분리 패턴)
- [08-debug-노하우.md](docs/08-debug-노하우.md) — **디버깅 24+ 카테고리** (Workflow / Code Review / Vault Path / 회의 protocol / Security / Time / LLM Prompt / Schedule / Plugins / External Apps / Cross-bot SoP)
- (예정) `05-meeting-thread-protocol.md` — 회의 신설 출처 기반 cross-check + Discord REST API thread + audience direct mention + 3-channel 병행 보고
- (예정) `07-codex-호출-layer.md` — `/tofu-at-codex` + codex-exec-bridge 패턴 + Hermes 호환 subprocess plugin

### Step 2. Claude Code 인증

```bash
claude auth login    # 🐧 👤 → 브라우저 인증
```

### Step 3. 첫 봇 wizard 시동

```bash
tmux new-session -s claude                # 🐧 👤
cd ~/<project> && claude                  # 🐧 🤖
```

Claude Code 안에서:

```
/thiscode:start                     # 🤖 wizard 진입
```

wizard 가 단계별 안내:
- Discord 봇 생성 (Developer Portal 이동)
- 봇 토큰 입력
- 첫 봇 페르소나 결정 (`soul.md` template)
- 페어링 + 첫 대화 검증

---

## 📚 커맨드 범례

본 레포의 코드블록에 자주 등장하는 아이콘:

| 아이콘 | 의미 |
|---|---|
| 🖥️ | Windows PowerShell |
| 🐧 | WSL Ubuntu / Linux 터미널 |
| 🤖 | Claude Code 가 자동 실행 |
| 👤 | 사용자가 직접 입력 |
| ✅ | 성공 |
| ❌→✅ | 실패 후 수정 |

---

## 🧩 레포 구조

```
thiscode/
├── install.sh                            # 환경 자동 detect + 10-step 자동화
├── README.md                              # 영문판 (default, 글로벌 사용자 대비)
├── README.ko.md                           # 본 파일 (한국어, vault-first)
├── LICENSE                                # MIT
├── CODEX_REVIEW.md                        # Codex 1차 adversarial review
├── CODEX_VERIFY.md                        # Codex 2차 verify (회복 후)
├── .claude-plugin/
│   ├── marketplace.json                   # thiscode-marketplace
│   └── plugin.json                        # thiscode v1.0
├── commands/                              # 슬래시 7종
│   ├── start.md                           # 메인 wizard (4-step 부트스트랩)
│   ├── install-hooks.md                   # SessionStart + UserPromptSubmit hook merge
│   ├── create-bot.md                      # 봇 디렉토리 + soul.md 자동 셋업
│   ├── add-bot.md
│   ├── open-meeting.md
│   ├── codex-check.md
│   └── self-update.md
├── skills/                                # 12 skill (vault-mirror 정책)
│   ├── knowledge-manager/                 # vault 풀 7-Layer Fusion (1161 줄)
│   ├── knowledge-manager-at/              # Agent Teams 변종 (1189 줄)
│   ├── knowledge-manager-lite/            # Lite 단일 에이전트 (530 줄)
│   ├── knowledge-manager-bootstrap/       # 4-Tier install 합본
│   ├── knowledge-manager-plain/           # headless variant
│   ├── search/                            # 4-Tier vault search
│   ├── search-lite/                       # 3-Tier (GraphRAG 의존 없음)
│   ├── codex-exec-bridge/                 # vault skill mirror (폴더)
│   ├── init/                              # onboarding wizard skill
│   ├── bootstrap/                         # plugin 설치 wizard
│   ├── meetings/                          # 회의실 4-file protocol
│   └── shared-memory/                     # 4-tier 메모리 정책
├── hooks/                                 # 봇 운영 hook 3종
│   ├── bot-session-init.sh                # SessionStart → soul.md 자동 inject
│   ├── discord-slash-cmd.sh               # UserPromptSubmit → 슬래시 강제
│   └── regression-self-check.sh           # 4-gate self-check 표 주입
├── templates/                             # 봇 페르소나 5종 + bot-roles-matrix · bot-checkup-checklist
│   ├── soul-general-assistant.md          # default 범용 비서
│   ├── soul-research-bot.md               # 자료조사·교차검증
│   ├── soul-writing-bot.md                # 글쓰기·퇴고
│   ├── soul-schedule-bot.md               # 일정·Todo·알람
│   ├── soul-custom.md                     # 자유 페르소나 + anatomy 가이드
│   └── discord-state-dir-README.md        # DISCORD_STATE_DIR 환경변수 구조
├── configs/                               # 우리 색깔 tmux.conf.local 등
│   └── tmux.conf.local
└── docs/                                  # 한국어 친절 가이드 (Zettelkasten 톤)
    ├── 03-shared-memory.md                # 4-tier 메모리
    ├── 04-obsidian-cli.md                 # 3-Tier 폴백
    ├── 06-claude-code-server.md           # headless + MCP server
    └── 08-debug-노하우.md                  # 디버깅 24+ 카테고리
```

`templates/bot-checkup-checklist.md` — 만든 봇이 적어둔 대로 움직이는지 7항으로 자가 점검(봇 생성 직후 1회, 이후 월 1회 권장).

---

## 🎯 사용 시나리오

### 시나리오 A. 새 머신 zero-state 셋업

WSL Ubuntu 또는 macOS 새로 깔린 머신에서, Claude Code 환경 처음 만들 때.

```bash
curl -fsSL https://raw.githubusercontent.com/treylom/ThisCode/main/install.sh | bash
```

### 시나리오 B. 봇 1개 추가 운영

이미 Claude Code 사용 중인 사용자가 Discord 봇으로 자기만의 페르소나 운영 시작.

- 첫 봇 `soul.md` 작성 (wizard 가 template 제공)
- Discord 봇 생성 + 페어링
- tmux session 운영 패턴 학습

### 시나리오 C. 신규 도입자 — 자기 속도로

처음 도입하는 사용자가 본 레포를 그대로 따라하며 자기 머신에 Claude Code + 봇 환경 셋업.

---

## 🔧 호환성

| 환경 | 지원 | 비고 |
|---|---|---|
| **WSL Ubuntu 20.04+** | ✅ primary | `install.sh` 가장 잘 테스트된 환경 |
| **Linux native** (Debian / Ubuntu / Fedora / Arch) | ✅ | 패키지 매니저 자동 detect |
| **macOS** | ✅ | brew 기반 |
| **Windows native** | ❌ | WSL 사용 권장 |

| Agent runtime | 호환 | 비고 |
|---|---|---|
| **Claude Code** | ✅ primary target | Anthropic 공식 CLI |
| Hermes Agent (NousResearch) | 🟡 부분 | SKILL.md 는 portable, Hermes plugin wrapper 는 추후 (deferred) |
| Codex CLI / Cursor / Gemini CLI / Goose 등 | 🟡 SKILL.md 만 | agentskills.io 표준 채택 — `name + description` 호환 |

---

## ⚠️ 트러블슈팅

### `nvm: command not found`

`source ~/.bashrc` 로 안 될 수도 있음. 새 터미널을 **완전히 닫고 다시 열기**.

### `permission denied` on `install.sh`

```bash
chmod +x install.sh
./install.sh
```

또는 `bash install.sh` 로 권한 없이도 실행.

### tmux 중첩 오류 (`sessions should be nested with care`)

이미 tmux 안에서 `claude` 실행한 경우. `Ctrl+B → c` 로 새 window 사용 (`ain` 함수가 자동 처리).

### git push rejected

원격에 다른 commit 이 있어 충돌:

```bash
git pull --rebase
git push
```

### Discord 봇 페어링 코드 만료

봇에 다시 DM → 새 코드 발급.

### soul.md 페르소나 "유령" (페르소나가 안 실림)

봇 답변에 페르소나가 반영되지 않는다면 SessionStart 훅이 등록되지 않았을 가능성이 큽니다:

```
/thiscode:install-hooks
```

기존 훅을 보존하면서 bot-session-init.sh 훅을 `~/.claude/settings.json`에 안전하게 병합합니다.

### GraphRAG 서버가 안 뜨는 경우 (vendor 의존 + ~/.cache venv)

```bash
bash scripts/install-graphrag.sh --check     # python3 + vendor SoT + requirements + venv + server health
bash scripts/install-graphrag.sh --preflight # Python 3.10+ / disk 5GB+ / port 8400 / vendor SoT 점검
bash scripts/install-graphrag.sh --apply     # venv 생성 + pip install + nohup uvicorn
```

`--apply` 의 동작:
- venv 위치 = `~/.cache/thiscode/graphrag/venv` (writable home cache)
- vendor SoT = `<thiscode>/vendor/graphrag/scripts/` (vault SoT 와 동등 박제, 21 file)
- requirements = `vendor/graphrag/scripts/requirements.txt` (7 deps: networkx / louvain / pyyaml / fastapi / uvicorn / numpy / httpx)
- entry = `uvicorn search_server:app --host 127.0.0.1 --port 8400` (background nohup)
- log = `~/.cache/thiscode/graphrag/run/graphrag.log`

---

## 🔬 내부 구조 (advanced)

### 훅 3종

- **`bot-session-init.sh`** (SessionStart) — `DISCORD_STATE_DIR` env 로 봇 자동 감지 → soul.md + 봇별 WD 메모리 + 공용 규율 주입
- **`discord-slash-cmd.sh`** (UserPromptSubmit) — 사용자 프롬프트 첫 줄이 `/cmd` 면 Skill 도구 호출 강제
- **`regression-self-check.sh`** (UserPromptSubmit) — 회귀 패턴 방지용 4게이트 자가점검 표 주입

### 스킬 (agentskills.io 표준)

- `init` — 온보딩 wizard (env 감지 + 8-Phase 추천)
- `bootstrap` — 설치 wizard 도우미
- `shared-memory` — 4-tier 메모리 정책 + Read-before-Edit
- `meetings` — 4-file 회의 프로토콜 + 출처 기반 크로스체크 + Discord REST API 스레드
- `slack-bridge` — Slack 브리지 운영·트러블슈팅 (발신자 게이트, 봇간 통신 허용목록, 라이브 회의 캔버스 레시피)
- `codex-exec-bridge` — Codex CLI 서브프로세스 + `/tofu-at-codex` 참조
- `knowledge-manager-at` — km-at Mode R 사전점검 (읽기 전용 진단 + dry-run 적용)

### Codex CLI 브리지

thiscode 는 Codex CLI 를 1급 브리지 층으로 포함합니다:

- `codex --version`·`codex exec --no-stream --model gpt-5.5` 를 서브프로세스로 실행
- 용도: 적대 검토, 코드 세컨드 오피니언, 대규모 병렬 리서치
- 검증: `/thiscode:codex-check`

### Custom Hybrid v1.0 에이전트 스펙

`schemas/agent-spec.json` 이 agentskills.io 기본 + Hermes `provides_*` + thiscode classroom 정책 + 동적 게이트 + 벤치마크 통합을 묶은 에이전트별 계약 레지스트리를 정의합니다. v1.0 은 `tier: core`(init wizard)와 km-at Mode R 사전점검 워크플로우용 `phases:` 를 추가했습니다.

---

## 🤝 기여

본 레포는 `treylom` 의 vault 운영 경험 종합. 

- PR / issue 환영
- 디버깅 노하우 공유 환영
- 사용자 피드백 환영

---

## 📄 라이선스

MIT — 자유 사용 / 자유 수정 / 자유 재배포.

상세: [LICENSE](LICENSE)

---

## 🔗 관련 자원

- **gpakosz/.tmux** (oh-my-tmux): https://github.com/gpakosz/.tmux
- **agentskills.io** (SKILL.md open standard): https://agentskills.io
- **Anthropic Claude Code**: https://www.anthropic.com/claude-code
- **NousResearch/hermes-agent**: https://github.com/NousResearch/hermes-agent
