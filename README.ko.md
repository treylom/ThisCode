![ThisCode — Tofu](assets/readme-banner.png)

# ThisCode

> Claude Code + Discord 봇 + codex 호출 통합 플러그인 — 개인 vault 자동화 + 멀티에이전트 운영
>
> 🌐 **English version**: [README.md](README.md) · 📘 **Setup**: [docs/SETUP.md](docs/SETUP.md) (개발자) · 🌱 [docs/SETUP-BEGINNER.md](docs/SETUP-BEGINNER.md) (초보자) · 🧩 [docs/AGENTS.md](docs/AGENTS.md) (Custom Hybrid v1.0) · ⚙️ **[설정 가이드](docs/SETUP-CONFIG-GUIDE.md)** (CLAUDE.md · soul.md · rules · Skills 2.0) · 🆕 **[최근 변경](docs/RECENT-CHANGES.md)** (설치 시 읽기 — AI가 자동 반영할 최신 변경 요약) · 📖 **[시작 안내서 (PDF)](docs/getting-started/ThisCode-ThisCodex-getting-started.pdf)** (초보자·한/영 병기) · 📄 **[전체 정리 한 장 (HTML)](docs/SUMMARY.html)** · 🤝 **[ThisCodex](https://github.com/treylom/ThisCodex)** (Codex 동반 런타임)

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

**Dependency provenance:** 16 entries 매트릭스 (Plugin 1 + Spec doc 2 + External tools 8 + Optional Dense 3 + Vendored Python runtime 1 + thiscode 1) [ATTRIBUTIONS.md](ATTRIBUTIONS.md) 안 명기. Cross-license compatibility Phase 1 GPT-5.5 review 검증 (MIT + Apache 2.0 + BSD-3 + Unlicense — 모두 permissive, copyleft zero).

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

## 선택: Discord 봇 + Agent Teams

본 플러그인의 Discord 봇 및 Agent Teams 통합은 선택사항입니다. vault-first 검색만으로도 완전히 작동하며, Discord 페어링 및 tmux 세션은 advanced use case 용입니다.

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
- `/thiscode:add-bot` — 추가 봇 1개 신설
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
- **orchestrator-watchdog** (`scripts/meeting_watchdog.py`) — **회의 진행 watchdog**: 회의 스레드 신설 시 ~5분마다 진행 점검, 목표+전체 작업 완료 시에만 자동 종료(Claude `/goal` 응용). fail-closed = 살아있는 회의 절대 잘못 종료 안 함. [05-meeting-thread-protocol.md](docs/05-meeting-thread-protocol.md) 와 짝
- [04-obsidian-cli.md](docs/04-obsidian-cli.md) — **Obsidian CLI 설정** (Mac brew / WSL Windows native / Linux snap·flatpak·deb) + 3-Tier 폴백 (CLI → MCP → Write/Read/Grep) + 알려진 버그·워크어라운드
- [06-claude-code-server.md](docs/06-claude-code-server.md) — **Claude Code 서버 기능** (`claude -p` 헤드리스 + MCP server + tmux session vs headless 분리 패턴)
- [08-debug-노하우.md](docs/08-debug-노하우.md) — **디버깅 24+ 카테고리** (Workflow / Code Review / Vault Path / 회의 protocol / Security / Time / LLM Prompt / Schedule / Plugins / External Apps / Cross-bot SoP)
- (예정) `05-meeting-thread-protocol.md` — 회의 신설 SOURCE FACT cross-check + Discord REST API thread + audience direct mention + 3-channel 병행 보고
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
├── templates/                             # 봇 페르소나 template
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
