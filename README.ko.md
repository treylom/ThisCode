![ThisCode — Tofu](assets/readme-banner.png)

# ThisCode

> Claude Code + Discord 봇 + codex 호출 통합 플러그인 — 개인 vault 자동화 + 멀티에이전트 운영
>
> **역할 경계**: ThisCode = 봇 하네스 운영 번들(운영 규칙·GraphRAG 운영 vendor·배포 계약). 범용 지식관리 제품은 [knowledge-manager](https://github.com/treylom/knowledge-manager), 플러그인 설치 창구는 [tofukyung-plugins](https://github.com/treylom/tofukyung-plugins)입니다.
>
> 지식관리와 vault 검색은 **km (knowledge-manager)** 플러그인이 제공합니다 — `claude plugin marketplace add treylom/tofukyung-plugins` + `claude plugin install km@tofukyung-plugins` 로 설치한 뒤 `/km:search` 와 `/km:knowledge-manager` 를 사용하세요. ThisCode 1.4.0 부터는 이 스킬들의 자체 사본을 포함하지 않습니다.
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

WSL / Linux / macOS 어디서든 `bash install.sh` 한 줄로 Claude Code + tmux 환경을 세팅합니다. **핵심 가치**: *구조화된 옵시디언 볼트* 안에서 *각 작업 디렉토리에 적합한 봇*을 두고, *디스코드*로 쓰며, *봇끼리 협업*하게 하는 것. 지식관리·볼트 검색은 km 플러그인이 맡고, ThisCode의 LLM 모델 라우팅과 봇 운영 기능은 그 봇들을 쓸모 있게 만드는 보조 기능입니다.

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
3. **Obsidian CLI** detect (Tier 2 — 미설치 시 manual download 안내)
4. **GraphRAG core** (Tier 1 — vendored Python runtime + 7-pkg pip install)
5. **Dense embedding** (옵션 4-channel — 사용자 confirm 1회, ~1GB)

Install 후: `bash scripts/healthcheck.sh` (6-phase 검증: superpowers + ripgrep + obsidian-cli + vault-search MCP + GraphRAG + Dense embedding).

**Windows 사용자:** 길이 둘입니다. **(a) 봇 페어링만 필요하면 — 네이티브 PowerShell 로 «지금» 됩니다.** Claude Code + Discord 플러그인의 *channels* 디렉터리(`~/.claude/channels/discord-<bot>/`)만 있으면 되고 **tmux·cmux·데몬이 전혀 필요 없습니다.** 봇 세션 = `DISCORD_STATE_DIR` 를 설정한 PowerShell 창에서 `claude` 를 띄운 것뿐입니다 ([docs/10-windows-powershell-bots.md](docs/10-windows-powershell-bots.md)). **(b) `install.sh` 전체 환경**(oh-my-tmux, 멀티세션 헬퍼)이 필요하면 — WSL 2 (Ubuntu 22.04+). Windows 에서 AI 어시스턴트가 설치를 대신 하고 있다면 **(a) 경로를 지정**하십시오 — 데몬이나 백그라운드 서비스로 tmux 를 재현하려 들면 안 됩니다.
>
> (a) 경로의 봇 기동은 PowerShell 창에서 이 두 줄입니다 — **`--channels` 플래그가 없으면 Discord 게이트웨이에 접속하지 않습니다**(무반응 최종 관문):
> ```powershell
> $env:DISCORD_STATE_DIR = "$HOME\.claude\channels\discord-<botname>"
> claude --channels plugin:discord@claude-plugins-official
> ```

**의존성 출처(Dependency provenance):** 20 entries 매트릭스 (Plugin 1 + Spec doc 2 + External tools 8 + optional GUI guide 1 + Optional Dense 3 + Vendored Python runtime 1 + Vendored prompt skill 1 + Vendored Slack bridge 1 + Vendored vault-search MCP 1 + thiscode 1) [ATTRIBUTIONS.md](ATTRIBUTIONS.md) 안 명기. Cross-license compatibility Phase 1 GPT-5.5 review 검증 (MIT + Apache 2.0 + BSD-3 + Unlicense — 모두 permissive, copyleft zero) — Slack bridge 항목은 저작권자 결정으로 MIT 통일(2026-08-06), 본 repo와 동일.

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
- **Phase 5**: 2000+ 노트 → km 플러그인 `/km:knowledge-manager-at` Mode R preflight (read-only 진단)
- **Phase 6-7**: advanced (Dashboard / 하이브리드 4채널)

> **GraphRAG = 환경 감지 + 선택사항** (사용자 spec). 노트 수 미충족 시도 force install 가능.

## 💬 플러그인 커맨드 & 스킬 도움말

각 플러그인 커맨드와 스킬에는 내장 도움말이 있습니다:

### 플러그인 커맨드

Claude Code 는 플러그인의 **`commands/` 와 `skills/` 를 둘 다** 슬래시로 발견합니다. **현재 세션에 실제 로드된 전량**은 Claude Code 에서 **`/` 를 입력해 `thiscode:` 로 필터**하거나 **내장 `/help`** 로 확인하십시오. 아래는 대표 진입점입니다:

- `/thiscode:start` — 초기 셋업 wizard (환경 인식, 봇 페어링, 검증)
- `/thiscode:init` — 경험자용 경량 셋업
- `/thiscode:add-bot` — 추가 Discord 봇 1개 신설 (soul.md 템플릿 + token + 페어링)
- `/thiscode:slack-configure` — Discord 대신(또는 추가로) Slack에 봇 연결 (claude-channel-server 브리지 자동 셋업)
- `/thiscode:km` — km (knowledge-manager) 플러그인 안내 (`/km:knowledge-manager`)
- `/thiscode:open-meeting` — 다봇 협업용 회의실 구조 생성
- `/thiscode:codex-check` — Codex CLI 브리지 연결 확인
- `/thiscode:install-hooks` (skill: `skills/install-hooks/SKILL.md`) — SessionStart / UserPromptSubmit / PreToolUse / Stop 훅의 등록 상태를 검사합니다 (**플러그인을 설치하면 훅은 이미 등록됩니다** — 동봉된 `hooks/hooks.json` 을 Claude Code 가 직접 싣습니다). 훅은 **봇 세션에서만**(`DISCORD_STATE_DIR` 이 있을 때) 동작하고, 일반 세션에서는 아무 출력도 동작 변화도 없습니다. 플러그인 설치본에서는 등록을 검사하고 옛 `~/.claude/settings.json` 병합 잔존을 정리하며(안 지우면 같은 훅이 두 번 발화), `hooks/hooks.json` 이 없는 체크아웃에서는 예전처럼 병합합니다. `/thiscode:create-bot` 이 같은 `scripts/install-hooks.sh` 를 대신 실행합니다.
- … 그 외 다수 — **`/thiscode:help` 가 설명과 함께 전량을 나열합니다** (문서에 박아둔 목록이 아니라, 실행 시점에 두 표면을 직접 훑습니다). `/` 를 입력해 `thiscode:` 로 필터해도 같습니다

### 스킬

각 스킬 (bootstrap, init, meetings, shared-memory 등)의 SKILL.md 에는 **"How to Use This Skill"** 절이 있어 언제 호출하는지, 무엇을 하는지 설명합니다. 지식관리·vault 검색 스킬은 이제 여기 포함되지 않습니다 — km (knowledge-manager) 플러그인을 설치해 `/km:knowledge-manager` · `/km:search` 를 쓰십시오.

---

## 선택: Discord 봇 + Agent Teams

본 플러그인의 Discord 봇 및 Agent Teams 통합은 선택사항입니다. km 플러그인의 볼트 검색은 독립적으로 작동하며, Discord 페어링 및 tmux 세션은 고급 다중 봇 운영에만 필요합니다.

> **Slack을 쓰고 싶다면?** Discord 대신(또는 추가로) Slack으로도 봇을 페어링할 수 있습니다 — `/thiscode:slack-configure` 실행 시 CLI 로그인·앱 설치 승인·토큰 입력 같은 사람 관문만 안내받고 나머지는 자동으로 처리됩니다. 상세: [skills/slack-configure/SKILL.md](skills/slack-configure/SKILL.md). 운영·트러블슈팅 참조: [skills/slack-bridge/SKILL.md](skills/slack-bridge/SKILL.md).

### Discord로 할 수 있는 것

봇을 한 번 페어링(연결)하면, Discord가 vault 봇들의 리모컨이 됩니다 — 터미널 없이도:

- **💬 멘션으로 작업 의뢰** — `@봇 오늘 노트 요약해줘` 하면 봇이 자기 세션에서 일하고 채널로 답해요.
- **🧵 스레드로 회의** — 스레드를 하나 열어 여러 봇이 협업. 각 봇이 공유 회의 문서를 같이 읽고 씁니다.
- **⏰ 잠든 봇 깨우기** — 조용해진 봇은 채널 메시지로 다시 깨웁니다 (신호는 항상 채널로 — 봇의 tmux에 입력을 직접 꽂는 건 금지, `rules/discord-comms.md` §5).
- **📎 파일·이미지 주고받기** — 스크린샷이나 문서를 첨부하면 봇이 받아서 작업해요.
- **🧹 세션 정리** — 사람(운영자)이 `/compact`·`/clear` 같은 세션 관리 명령을 봇 tmux 세션에 직접 보내 컨텍스트를 비울 수 있어요 (`rules/discord-comms.md` §5 R5).

> 여기 적은 건 일상적으로 자주 쓰는 동작이에요. 채널 모드로 세션을 더 정교하게 다루는 모델(Admin / Main / Session 라우팅)은 [`docs/connector-session-ux.md`](docs/connector-session-ux.md) 참고.

---

## 📊 과거 기준선: ThisCode 로컬 검색 도구 benchmark

이 절은 2026-05-13 ThisCode legacy 로컬 검색 도구 기준선입니다.
`benchmark/results/2026-05-13.json`에는 해당 날짜 실행 메타데이터가 남아 있지만
Tier 1·2를 건너뛰었으므로 과거 문서의 모든 수치를 검증하는 자료는 아닙니다.
km 플러그인의 현재 runtime 성능 측정이 아니며, 현재 vault 검색은 `/km:search`를
사용하십시오. 이 저장소에는 GraphRAG·vault-search
MCP·Obsidian CLI·ripgrep의 성능 특성을 비교하는 개발자용 benchmark runner도 남아
있으므로 **본인 vault에서 직접 측정**해 환경별 차이를 확인할 수 있습니다.
연결된 benchmark 가이드는 당시 legacy engine ID(vault-search MCP는 2,
Obsidian CLI는 3)를 보존하며, 현재 km 순서는 아래에 따로 적었습니다.

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

**Tier 순서:** Tier 1 [GraphRAG](docs/SETUP.md#tier-1) → Tier 2 [Obsidian CLI](docs/SETUP.md#tier-2) → Tier 3 [vault-search MCP](docs/SETUP.md#tier-3) → Tier 4 [ripgrep](docs/SETUP.md#tier-4). 정확도 우선 fallback.

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
| 6.5 | **Obsidian CLI** (Mac brew cask / WSL Windows native / Linux snap·flatpak·deb) — Tier 2 fallback | brew / snap / 수동 |
| 7 | Claude Code plugin install 안내 (marketplace 등록 + `commands/`·`skills/` 두 발견 표면의 슬래시) | (Claude Code 안 슬래시) |
| 8 | 첫 봇 wizard 안내 (`/thiscode:start`) | (Claude Code 안 슬래시) |

Claude Code 는 플러그인의 **`commands/*.md` 와 `skills/<name>/SKILL.md` 를 둘 다** 슬래시로 발견합니다 — `skills/` 쪽도 `/thiscode:<name>` 으로 바로 호출됩니다.

> **전체 목록은 `/thiscode:help` 로 보십시오** — 설명까지 붙여 전량을 나열합니다. 이 문서에 목록을 박아두지 않는 이유는, 박으면 명령이 하나 늘 때마다 낡고 그 낡음이 아무 신호도 내지 않기 때문입니다. `help` 는 **실행 시점에** `commands/*.md` 와 `skills/<이름>/SKILL.md` 를 직접 훑습니다. (Claude Code 에서 `/` 를 입력해 `thiscode:` 로 필터하거나 **내장 `/help`** 를 써도 같은 목록을 볼 수 있습니다.)

아래는 **대표 진입점**입니다:

- `/thiscode:start` — 메인 wizard (환경 인식 + Discord 봇 셋업 + 첫 대화 검증)
- `/thiscode:install-hooks` (skill: `skills/install-hooks/SKILL.md`) — 플러그인이 `hooks/hooks.json` 으로 이미 등록한 SessionStart + UserPromptSubmit + **Stop(회의 재독)** 훅을 검사하고, 옛 `~/.claude/settings.json` 병합 잔존을 정리합니다(기존 사용자 훅 보존). 봇 세션 밖에서는 조용히 통과합니다.
- `/thiscode:create-bot` — 신규 봇 디렉토리 + soul.md template 셋업
- `/thiscode:add-bot` — 추가 Discord 봇 1개를 기존 셋업에 신설
- `/thiscode:create-slack-bot` — Slack 워크스페이스 연결 (claude-channel-server 브리지 자동 셋업, 별칭: `/thiscode:slack-configure`)
- `/thiscode:km` — km (knowledge-manager) 플러그인 안내 (`/km:knowledge-manager` · `/km:search`)
- `/thiscode:open-meeting` — 회의실 폴더 신설 (다 봇 협업 4-file)
- `/thiscode:codex-check` — Codex CLI 설치 + OAuth 인증 + 모델 picker 검증
- … 그 밖에 다수 (`/` → `thiscode:` 필터로 현재 세션의 전량 확인)

> ℹ️ **훅은 플러그인 설치와 함께 등록됩니다**(`hooks/hooks.json` 동봉). 단 **봇 세션에서만** 동작하므로, `DISCORD_STATE_DIR` 없이 켠 세션에서는 soul.md 가 주입되지 않습니다 — 그건 고장이 아니라 설계입니다. 등록 상태가 궁금하면 `/thiscode:install-hooks` 스킬로 검사하세요.

순정 Claude Code 부트스트랩 (hook + 봇 없는 상태):

```
1. /thiscode:install-hooks   # install-hooks 스킬: SessionStart + UserPromptSubmit + Stop(회의 재독) hook 등록
2. /thiscode:add-bot         # 첫 봇 디렉토리 + soul.md 셋업
3. /thiscode:start           # 메인 wizard (Discord 페어링 + 첫 대화 검증)
4. /thiscode:codex-check     # Codex CLI 활성 확인 (선택)
```

## 📦 운영 노하우 가이드 (docs/)

thiscode 가 packaging 한 우리 vault 운영 노하우:

- [03-shared-memory.md](docs/03-shared-memory.md) — **공유 메모리 4-tier** (T1 git-tracked / T2 machine-specific / T3 project-meetings / T4 per-bot WD)
- [memory-dreaming.md](docs/memory-dreaming.md) — **메모리 정리(지우지 않고 옮김) 쉬운 설명**: 안 쓰는 메모리를 작업공간 밖 보관소로 *옮기고* 명령 한 줄로 *되돌립니다*(체크섬 검증). 9칸 전부 같은 기준표(Codex 포함)·보수적(자동이동 실측 0건·애매하면 사람검토)·기준은 자기 실수서 학습. 도구 `scripts/memory_dreaming.py`(`--scan` 기본 미리보기 / `--apply` 게이트 / `--restore`), 주1회 강제(YAML+세션시작 경고+launchd 3중)
- **orchestrator-watchdog** (`scripts/meeting_watchdog.py`) — **회의 진행 watchdog (회의마다 권장 — 감시 봇 1개 초대, 첫 dispatch 전에 가동)**: 회의 스레드 신설 시 ~5분마다 진행 점검(메인테이너 vault 는 ~3분 운영), 목표+전체 작업 완료 시에만 자동 종료(Claude `/goal` 응용). fail-closed = 살아있는 회의 절대 잘못 종료 안 함. [05-meeting-thread-protocol.md](docs/05-meeting-thread-protocol.md) §2.3 + [rules/meeting-protocol.md](rules/meeting-protocol.md) §5 와 짝
- [04-obsidian-cli.md](docs/04-obsidian-cli.md) — **과거 Obsidian CLI 설정 가이드** (기존 로컬 3-Tier CLI → MCP → Write/Read/Grep 흐름; 현재 km 계약은 별도 문서 참조) + 알려진 버그·워크어라운드
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
│   └── plugin.json                        # thiscode v1.4.1
├── commands/                              # 슬래시 발견 표면 ①
│   ├── start.md                           # 메인 wizard (4-step 부트스트랩)
│   ├── add-bot.md                         # 추가 Discord 봇 신설
│   ├── slack-configure.md                 # Slack 연결
│   ├── open-meeting.md · codex-check.md
│   └── …                                  # 전량은 `/` → thiscode: 필터로
├── skills/                                # 슬래시 발견 표면 ② (vault-mirror 정책)
│                                          #    skills 도 /thiscode:<name> 으로 직접 호출된다
│                                          #    install-hooks · create-bot · create-slack-bot ·
│                                          #    self-update · help 가 여기 산다
│   ├── codex-exec-bridge/                 # vault skill mirror (폴더)
│   ├── init/                              # onboarding wizard skill
│   ├── bootstrap/                         # plugin 설치 wizard
│   ├── meetings/                          # 회의실 4-file protocol
│   ├── shared-memory/                     # 4-tier 메모리 정책
│   └── …                                  # 전량은 `/` → thiscode: 필터로
├── hooks/                                 # 봇 운영 hook 7종
│   ├── bot-session-init.sh                # SessionStart → soul.md 자동 inject
│   ├── discord-slash-cmd.sh               # UserPromptSubmit → 슬래시 강제
│   ├── regression-self-check.sh           # 4-gate self-check 표 주입
│   ├── rule-router.sh                      # UserPromptSubmit → 규칙 라우팅
│   ├── dispatch-room-gate.py               # PreToolUse → 공용 채널 봇 응답 점검
│   ├── meeting-stop-reread.sh              # Stop → 활성 회의 marker 재확인
│   └── reply-gate.sh                       # Stop → 최종 답변 gate
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
| **Windows native (PowerShell)** | ✅ 봇 페어링 | Discord 봇 페어링이 Claude Code **channels**(`~/.claude/channels/`)로 네이티브 동작 — **tmux / cmux / 데몬 불필요.** 기동 = `$env:DISCORD_STATE_DIR` 설정 후 `claude --channels plugin:discord@claude-plugins-official` (**`--channels` 없으면 미접속**). tmux 기반 부가물(oh-my-tmux, `install.sh` 멀티세션 헬퍼)만 여전히 WSL 필요 — [docs/10-windows-powershell-bots.md](docs/10-windows-powershell-bots.md) 참조 |

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

봇 답변에 페르소나가 반영되지 않는다면 SessionStart 훅이 그 세션에 닿지 않은 것입니다. 플러그인이 설치 시 등록해 두고 훅은 `DISCORD_STATE_DIR` 이 없으면 일부러 조용히 지나가므로, 흔한 원인은 둘 — 그 변수 없이 켠 세션이거나, 플러그인이 꺼져 있는 경우입니다. 등록 상태 검사:

```
/thiscode:install-hooks   # install-hooks 스킬 실행
```

`skills/install-hooks/SKILL.md` 스킬은 `hooks/hooks.json` 에 `bot-session-init.sh` 가 실려 있고 그 파일이 실제로 있는지 확인하고, 옛 병합 경로가 `~/.claude/settings.json` 에 남긴 중복 항목을 제거합니다 — 사용자가 직접 넣은 훅은 보존하고, 파일명만 같고 ThisCode 소유 표식이 없는 항목은 지우지 않고 「손으로 검토」 경고로만 보여줍니다.

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
