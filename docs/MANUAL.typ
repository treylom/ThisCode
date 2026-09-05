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
]
#show raw.where(block: true): it => block(
  fill: rgb("#f6f8fa"), inset: 8pt, radius: 4pt, width: 100%, it
)

#align(center)[
  #v(1.5em)
  #text(size: 24pt, weight: "bold")[thiscode 매뉴얼]
  #v(0.3em)
  #text(size: 14pt, fill: rgb("#555"))[설치 + 핵심 기능 8 sections]
  #v(1em)
  #box(fill: rgb("#f0f4ff"), inset: 12pt, radius: 6pt, width: 80%)[
    #align(left)[
      #text(weight: "bold")[용어 모르겠으면?] → docs/GLOSSARY.md (30+ 용어 풀이)
      #v(0.3em)
      #text(weight: "bold")[더 친절한 가이드?] → SETUP-BEGINNER.md (분기 친절)
    ]
  ]
  #v(0.5em)
  #text(size: 9pt, fill: rgb("#888"))[v1.0 통합 첫 출시]
]

#pagebreak()

= thiscode 가 뭐예요?

Claude Code + Discord 봇 + Codex 호출을 묶은 봇 운영(bot-harness operations) 플러그인. 지식관리와 vault 검색은 km 플러그인이 담당합니다.

== 차별점 한 줄

ThisCode는 봇 운영·설치·회의·공유 메모리·모델 라우팅에 집중하고, 지식관리와 vault 검색은 km 플러그인이 맡습니다.

= 설치 — ThisCode + km 플러그인

```bash
# 1. Prereq (node 18+, jq, git)
# 2. ThisCode bot-harness install
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode

# 3. km plugin install
claude plugin marketplace add treylom/tofukyung-plugins
claude plugin install km@tofukyung-plugins

# 4. Claude Code에서 km 저장 위치·MCP·설정 구성: /km:setup
#    (검색 Tier 설치 명령이 아님)

# 5. Tier 4 ripgrep (로컬 도구)
bash ~/.claude/plugins/thiscode/scripts/install-ripgrep.sh --apply

# 6. Tier 2 Obsidian CLI 감지·Obsidian 앱 안내 (선택)
bash ~/.claude/plugins/thiscode/scripts/install-obsidian-cli.sh

# 7. 별도 로컬 임베딩 도구 vault-search MCP (선택; km Tier 아님)
bash ~/.claude/plugins/thiscode/scripts/install-vault-search.sh --apply

# 8. Tier 1 GraphRAG (선택, advanced)
bash ~/.claude/plugins/thiscode/scripts/install-graphrag.sh --apply

# 9. ThisCode bot-harness healthcheck
bash ~/.claude/plugins/thiscode/scripts/healthcheck.sh
```

로컬 검색 도구 설치는 ThisCode의 스크립트가 담당하고, km 플러그인의 `/km:search`가 검색 fallback을 실행합니다. Claude Code에서 `/km:setup`을 별도로 실행해 km 저장 위치·MCP·설정을 구성합니다.

자세한 분기 가이드: SETUP-BEGINNER.md

= 4-Tier Search

로컬 도구 설치는 ThisCode의 `scripts/install-*.sh`, 검색 실행은 km의
`/km:search`, 저장 위치·Obsidian MCP·설정은 `/km:setup`이 담당합니다.
km 검색 순서는 GraphRAG → Obsidian CLI → Obsidian MCP → 텍스트 검색입니다.
별도 vault-search MCP 설치 여부는 km의 어느 Tier도 대신하지 않습니다.

_아래는 옛 로컬 도구 안내의 설명용 기대값이며 측정 결과가 아닙니다._
숫자는 km 검색 단계와 대응시키지 않습니다. 보관된
`benchmark/results/2026-05-13.json`은 당시 엔진 ID 1(GraphRAG)·2(vault-search
MCP)를 건너뛴 실행 기록으로, 이 기대값이나 현재 km 성능을 검증하지 않습니다.

#table(
  columns: (1fr, auto, auto, auto),
  inset: 6pt,
  align: (left, center, center, center),
  fill: (_, row) => if row == 0 { rgb("#f0f4ff") } else { none },
  [옛 로컬 도구], [속도 기대값], [정확도 기대값], [셋업 기대값],
  [GraphRAG (LLM + graph)], [1500-3000ms], [매우 높음], [25분],
  [obsidian-cli (Obsidian index)], [200-500ms], [중간], [3분],
  [vault-search MCP (embedding)], [500-1000ms], [높음], [5분],
  [ripgrep (literal)], [30-100ms], [낮음], [0분],
)

현재 검색 단계의 조건과 실행은 km 플러그인의 `/km:search`를 따릅니다.

= Knowledge Manager (km plugin)

지식관리·검색은 ThisCode에 내장되지 않습니다. km 플러그인을 설치한 뒤 다음 명령을 사용합니다.

- `/km:search` — vault 검색과 fallback
- `/km:knowledge-manager` — 지식관리·수집·분류·저장
- `/km:setup` — km 플러그인 설정 생성·재설정

#pagebreak()

= LLM 모델 routing

검색 결과 후 응답 생성 시 task complexity 따라 모델 자동 선택:

#table(
  columns: (auto, auto, auto, 1fr),
  inset: 7pt,
  align: (left, center, center, left),
  fill: (_, row) => if row == 0 { rgb("#f0f4ff") } else { none },
  [Task], [Claude], [Codex], [예시],
  [단순], [Haiku], [gpt-5.5], ["NuriFlow ARR"],
  [중간], [Sonnet], [gpt-5.5-codex], ["Q1 보고서 핵심 3가지 요약"],
  [종합], [Opus[1m]], [gpt-5.5-codex-spark], ["ARR 와 팀 size 상관관계 추론"],
)

`scripts/route-model.mjs` heuristic (query length + 키워드). user override `--model haiku|sonnet|opus`.

= 회의실 / Codex Bridge / 공유메모리 / Hook

- `/thiscode:meetings` — 회의록 폴더 + 4-file template 자동
- `/codex` — OpenAI Codex 호출 bridge (second opinion)
- shared-memory — 4-tier 공유 메모리 (T1 git / T2 machine / T3 project / T4 per-bot)
- SessionStart hook — soul.md 자동 inject

= 5-axis Benchmark

5 차원 측정 — latency_ms / recall_precision / cost_tokens / setup_time_min / kg_depth.

```bash
VAULT=~/your-vault bash benchmark/runners/run-all.sh
python3 benchmark/report-generator.py --print-only
```

자세한 측정 방법 + 해석: BENCHMARK.md

= FAQ + GLOSSARY 참조

자주 묻는 질문 7개: SETUP-BEGINNER.md FAQ section

용어 풀이 (LLM / MCP / CEL / embedding / precision / kg_depth / fallback / dispatcher / RAG 등 30+): GLOSSARY.md
