#set page(paper: "a4", margin: (x: 2cm, y: 2.2cm), numbering: "1")
#set text(font: ("Apple SD Gothic Neo", "Helvetica Neue"), size: 10.5pt, lang: "ko")
#set par(leading: 0.8em, justify: true)
#set heading(numbering: "1.")
#show heading.where(level: 1): it => block(breakable: false)[
  #v(0.5em)
  #text(size: 16pt, weight: "bold", fill: rgb("#1a4d8c"))[#it]
  #v(0.2em)
  #line(length: 100%, stroke: 0.5pt + rgb("#1a4d8c"))
  #v(0.3em)
]
#show heading.where(level: 2): it => block(breakable: false)[
  #v(0.3em)
  #text(size: 13pt, weight: "bold", fill: rgb("#2c3e50"))[#it]
  #v(0.2em)
]
#show raw.where(block: true): it => block(
  fill: rgb("#f6f8fa"),
  inset: 8pt,
  radius: 4pt,
  width: 100%,
  it,
)

#align(center)[
  #v(2em)
  #text(size: 26pt, weight: "bold")[thiscode 짱쉬운 셋업 가이드]
  #v(0.5em)
  #text(size: 16pt, fill: rgb("#555"))[처음 써보는 분도 5단계로 완성]
  #v(2em)
  #box(fill: rgb("#f0f4ff"), inset: 14pt, radius: 6pt, width: 80%)[
    #align(left)[
      #text(weight: "bold")[이 가이드의 대상]
      #v(0.3em)
      터미널을 거의 안 써본 분도 OK. 한 줄씩 복사 + 붙여넣기 + Enter 만 하면 됩니다.
      #v(0.5em)
      #text(weight: "bold")[준비물]
      #v(0.3em)
      - 인터넷 연결된 컴퓨터 (Mac / Linux / WSL — Windows native 는 추후 지원)
      - Claude Code (https://claude.com/code 에서 설치)
      - 5\~30분 (선택한 Tier 에 따라)
    ]
  ]
  #v(1em)
  #text(size: 10pt, fill: rgb("#888"))[2026-05-13 작성 | v1.0]
]

#pagebreak()

= 시작하기 전에 — 전체 흐름 그림

한 줄로 요약하면 이렇게 흘러갑니다:

#v(0.3em)
#box(fill: rgb("#fffaf0"), inset: 10pt, radius: 4pt, width: 100%)[
  #text(weight: "bold")[0. 환경 점검] $arrow$ #text(weight: "bold")[1. 플러그인 설치] $arrow$ #text(weight: "bold")[2. 검색 MCP] $arrow$ #text(weight: "bold")[3. Obsidian 분기] $arrow$ #text(weight: "bold")[4. GraphRAG (선택)] $arrow$ #text(weight: "bold")[5. healthcheck]
]

#v(0.5em)

각 단계 끝에 #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ 여기까지 되면 정상] 체크포인트가 있습니다. 안 되면 해당 단계에서 멈추고 다음으로 넘어가지 마세요.

#v(0.5em)

== km 플러그인의 4-Tier 검색이 뭔가요?

km 플러그인의 4-Tier 검색은 GraphRAG → Obsidian CLI → vault-search MCP →
ripgrep 순으로 시도합니다. 한 Tier가 미설치이거나 결과가 부족하면 다음
Tier로 fallback하며, 로컬 도구는 thiscode 설치 스크립트로 설치합니다.

#box(fill: rgb("#f8f9fa"), inset: 10pt, radius: 4pt, width: 100%)[
  - #text(weight: "bold")[Tier 4 — ripgrep] (기본, 0분 셋업) — 문자열 일치, 매우 빠름
  - #text(weight: "bold")[Tier 2 — obsidian-cli] (3분 셋업, Obsidian 사용자만) — Obsidian index 활용
  - #text(weight: "bold")[Tier 3 — vault-search MCP] (5분 셋업) — embedding semantic 검색
  - #text(weight: "bold")[Tier 1 — GraphRAG] (25분 셋업, advanced) — LLM + graph + 가장 정확
]

#v(0.5em)

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[Tip] — 빠르게 도입하려면 Tier 4 + 2 까지만 (3-A) 충분합니다. 익숙해진 후 GraphRAG (4-C) 도전.
]

#pagebreak()

= 0단계: wizard 진입 (v2.1 추천)

가장 쉬운 방법은 `thiscode init` wizard — vault / 도구 / 자원 자동 감지 + 8 Phase 추천.

```bash
bash ~/.claude/plugins/thiscode/scripts/claude-discode-init.sh
```

wizard 가 물어보는 항목:
- 어떤 Tier 의 검색 도구를 install?
- GraphRAG install? (500+ 노트 권장, 단 옵션 언제나)
- Mode R preflight? (2000+ 노트 권장, read-only)

자세한 단계별 install 은 아래 1~5 단계 참고. (wizard 진입 안 한 사용자 위함)

#pagebreak()

= Step 0 — 환경 점검 (2분)

먼저 컴퓨터에 뭐가 깔려있는지 확인합니다. 터미널을 열고 (Mac = Spotlight `cmd+space` → "터미널" 검색 / WSL = Ubuntu 앱 / Linux = Ctrl+Alt+T) 아래 명령을 한 줄씩 복사 + 붙여넣기 + Enter.

#v(0.5em)

== 0-1. Node.js 확인

```bash
node --version
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ 성공 모습] — `v18.17.0` 같은 숫자가 보이면 OK
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ 실패 시] — "command not found" 가 나오면 https://nodejs.org 에서 LTS 버전 (v18 또는 v20) 설치 후 터미널 재시작
]

#v(0.5em)

== 0-2. jq 확인

```bash
jq --version
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ 성공 모습] — `jq-1.6` 같은 출력
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ 실패 시] — Mac = `brew install jq` / Ubuntu/WSL = `sudo apt install jq`
]

#v(0.5em)

== 0-3. git 확인

```bash
git --version
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ 성공 모습] — `git version 2.x.x`
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ 실패 시] — Mac = `xcode-select --install` / Ubuntu/WSL = `sudo apt install git`
]

#pagebreak()

= Step 1 — 플러그인 설치 (2분)

```bash
mkdir -p ~/.claude/plugins
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode
```

#v(0.3em)

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ 성공 모습]
  ```
  Cloning into '/Users/.../thiscode'...
  remote: Enumerating objects: ...
  Receiving objects: 100% (...), done.
  ```
]

#v(0.3em)

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ 실패 시]
  - "Permission denied" → `mkdir ~/.claude/plugins` 권한 확인
  - "already exists" → 이미 설치됨. `cd ~/.claude/plugins/thiscode && git pull` 로 update
]

= Step 2 — 검색 MCP 설치 (5분, 권장)

```bash
bash ~/.claude/plugins/thiscode/scripts/install-vault-search.sh --apply
claude mcp list | grep vault-search
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ 성공 모습] — `vault-search` 항목 1줄 출력
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ 실패 시]
  - `claude: command not found` $arrow$ Claude Code 미설치. https://claude.com/code
  - npm install 실패 $arrow$ `nvm use 18` 또는 `nvm install 18` 시도
]

#box(fill: rgb("#fff8e1"), inset: 10pt, radius: 4pt)[
  #text(weight: "bold")[중요] — 설치 후 Claude Code 를 한 번 재시작하세요 (`exit` 후 재실행).
]

= Step 3 — Obsidian 쓰시나요? 🤔

#box(fill: rgb("#fff8e1"), inset: 12pt, radius: 6pt, width: 100%)[
  #text(weight: "bold")[예] $arrow$ 3-A (Obsidian CLI 설치, 3분)
  #v(0.3em)
  #text(weight: "bold")[아니오] $arrow$ 3-B (SKIP, 바로 Step 4)
]

== 3-A. Obsidian CLI 설치 (Obsidian 사용자만)

```bash
bash ~/.claude/plugins/thiscode/scripts/install-obsidian-cli.sh
which obsidian-cli
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ 성공 모습] — `/usr/local/bin/obsidian-cli` path 출력
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ 실패 시] — `sudo` 추가 또는 README 의 manual install 참고
]

== 3-B. SKIP — Obsidian 없이도 잘 작동 ✅

- 4-Tier 중 Tier 2 (Obsidian CLI) 만 SKIP
- 나머지 Tier 1 / 3 / 4 정상 작동, 기능 80% 동일
- 바로 Step 4 로 진행

#pagebreak()

= Step 4 — GraphRAG 까지 가실래요? 🚀

3가지 옵션 중 선택:

#table(
  columns: (auto, 1fr, auto),
  inset: 8pt,
  align: (left, left, center),
  fill: (_, row) => if row == 0 { rgb("#f0f4ff") } else { none },
  [#text(weight: "bold")[선택]], [#text(weight: "bold")[누가?]], [#text(weight: "bold")[시간]],
  [4-A], [지금은 패스, 빠르게 도입 (Tier 2 까지만)], [0분],
  [4-B], [도커 익숙한 사용자], [10분],
  [4-C], [Python 로컬 + 직접 디버깅 원함], [25분],
)

== 4-A. 지금은 패스 ✅

$arrow$ 바로 Step 5 로

== 4-B. 도커로 간편 설치

```bash
docker --version
docker pull ghcr.io/treylom/ThisCode-graphrag:v1.0
docker run -d -p 8400:8400 -v ~/vault:/vault \
  --name thiscode-graphrag \
  ghcr.io/treylom/ThisCode-graphrag:v1.0
curl localhost:8400/health
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ 성공 모습] — `{"status":"ok"}`
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ 실패 시]
  - Docker 미설치 $arrow$ https://docs.docker.com/get-docker/
  - port 8400 충돌 $arrow$ `-p 8401:8400` 변경 + `GRAPHRAG_URL=http://localhost:8401` env 설정
]

== 4-C. Python 로컬 설치

```bash
python3 --version
bash ~/.claude/plugins/thiscode/scripts/install-graphrag.sh --apply
curl localhost:8400/health
```

설치 시간 5\~10분 + 첫 indexing 15분 = 총 \~25분.

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ 성공 모습] — `{"status":"ok"}`
]

#pagebreak()

= Step 5 — 모든 게 잘 됐는지 확인 🎉

```bash
bash ~/.claude/plugins/thiscode/scripts/healthcheck.sh
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ 성공 모습 — 본인 선택에 따라 SKIP 표기]
  ```
  thiscode healthcheck v1.0
  ─────────────────────────────────
  ✓ Tier 4 (ripgrep)  : OK
  ✓ Tier 3 (MCP)      : OK
  ○ Tier 2 (CLI)      : SKIP (Obsidian 미사용 — 3-B 선택)
  ○ Tier 1 (GraphRAG) : SKIP (4-A 선택)
  ─────────────────────────────────
  all required checks passed ✅
  ```
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ 실패 시]
  ```bash
  cat ~/.thiscode-setup.log
  ```
  이 파일 내용을 복사해서 GitHub Issue 등록:
  https://github.com/treylom/ThisCode/issues/new?template=setup-failure.yml
]

= 첫 사용 해보기

Claude Code 안에서:

```
/thiscode:help
```

vault 검색을 써 보려면 km 플러그인을 먼저 설치합니다:

```
claude plugin marketplace add treylom/tofukyung-plugins
claude plugin install km@tofukyung-plugins
/km:search "안녕 첫 검색"
```

축하합니다! 🎉

#pagebreak()

= 자주 묻는 질문

== Q1. 셋업 도중 중간에 멈춰도 되나요?

네. 각 단계가 독립적이라 1-3단계까지만 해도 Tier 4 (ripgrep) 검색은 작동합니다.

== Q2. macOS / Linux / Windows / WSL 다 됩니까?

macOS / Linux / WSL 은 검증 완료. Windows native 는 추후 지원 예정 (현재 WSL 권장).

== Q3. 학생인데 비용 걱정?

- Tier 4 (ripgrep) + Tier 2 (Obsidian) = 100% 무료
- Tier 3 (MCP) = 무료 (Claude Code 구독 안에)
- Tier 1 (GraphRAG) = OpenAI/Anthropic API 호출 → 본인 vault 크기에 따라 1회 indexing \$0.5\~5

== Q4. 이미 obsidian-cli 만 쓰고 있는데 차이는?

README 의 5-axis benchmark 표 참고. 예전 ThisCode 가이드 메모에는 당시
Obsidian CLI 기준선보다 GraphRAG recall이 높다고 적혀 있었지만, 보관된
2026-05-13 결과는 legacy engine ID(vault-search MCP는 2, Obsidian CLI는 3)로
Tier 1·2를 건너뛰어 정확한 상승률을 입증하지 않습니다.
이 메모는 역사적 기록이며 현재 km 플러그인 runtime 성능 측정이 아닙니다.
- 현재 trade-off: Tier 2 Obsidian CLI는 가벼운 로컬 선택지이고, Tier 1
  GraphRAG는 semantic/graph 검색과 더 큰 셋업·API 비용을 동반합니다.
- 두 선택지는 본인 fixture로 비교하고, 역사적 상승률은 재사용하지 마세요.
- 단 setup 25분 + LLM 비용

== Q5. 피드백 어디 남기나요?

GitHub Discussions Feedback category: https://github.com/treylom/ThisCode/discussions/categories/feedback

5 질문 schema 로 2분 응답 → v1.1 graduate decision 에 반영됩니다.

#v(2em)

#align(center)[
  #box(fill: rgb("#f0f4ff"), inset: 14pt, radius: 6pt, width: 70%)[
    #text(weight: "bold")[도움이 필요하면]
    #v(0.5em)
    - GitHub Issue: https://github.com/treylom/ThisCode/issues
    - 커뮤니티: GitHub Discussions
    - 문서: SETUP.md (개발자용) / AGENTS.md (Custom Hybrid v1.0 spec) / BENCHMARK.md (5-axis 해석)
  ]
]
