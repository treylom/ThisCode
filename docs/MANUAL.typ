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

Claude Code + Discord 봇 + Codex 호출 + 4-Tier vault search 가 통합된 Knowledge Manager 플러그인.

== 차별점 한 줄

기존 도구 (obsidian-cli 단독 / `/search` 단독 / `/vault-search` 단독) 를 4-Tier fallback 으로 자동 cascading. 빠른 도구 먼저 → 결과 부족 시 정확한 도구로.

= 설치 — 5단계

```bash
# 1. Prereq (node 18+, jq, git)
# 2. Plugin install
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode

# 3. Tier 2 MCP (5분, 권장)
bash ~/.claude/plugins/thiscode/scripts/install-vault-search.sh --apply

# 4. Tier 3 Obsidian CLI (선택, Obsidian 사용자만)
bash ~/.claude/plugins/thiscode/scripts/install-obsidian-cli.sh

# 5. Tier 1 GraphRAG (선택, advanced 25분)
bash ~/.claude/plugins/thiscode/scripts/install-graphrag.sh --apply

# 6. Healthcheck
bash ~/.claude/plugins/thiscode/scripts/healthcheck.sh
```

자세한 분기 가이드: SETUP-BEGINNER.md

= 4-Tier Search

#table(
  columns: (auto, 1fr, auto, auto, auto),
  inset: 6pt,
  align: (center, left, center, center, center),
  fill: (_, row) => if row == 0 { rgb("#f0f4ff") } else { none },
  [Tier], [도구], [속도], [정확도], [셋업],
  [1], [GraphRAG (LLM + graph)], [1500-3000ms], [매우 높음], [25분],
  [2], [vault-search MCP (embedding)], [500-1000ms], [높음], [5분],
  [3], [obsidian-cli (Obsidian index)], [200-500ms], [중간], [3분],
  [4], [ripgrep (literal)], [30-100ms], [낮음], [0분],
)

dispatcher 가 Tier 1 시도 → 결과 부족 시 Tier 2 → ... 순서 fallback.

= Knowledge Manager (KM)

3 variant:

- `/thiscode:km` (lite, default) — 개인 vault
- `/thiscode:km at` (experimental) — 팀 vault + Agent Teams
- `/thiscode:km plain` (internal) — CI/cron headless

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
