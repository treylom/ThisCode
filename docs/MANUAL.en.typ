#set page(paper: "a4", margin: (x: 2cm, y: 2.2cm), numbering: "1")
#set text(font: ("Helvetica Neue", "Apple SD Gothic Neo"), size: 10.5pt, lang: "en")
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
  #text(size: 24pt, weight: "bold")[thiscode Manual]
  #v(0.3em)
  #text(size: 14pt, fill: rgb("#555"))[Install + Core Features in 8 sections]
  #v(1em)
  #box(fill: rgb("#f0f4ff"), inset: 12pt, radius: 6pt, width: 80%)[
    #align(left)[
      #text(weight: "bold")[Don't know a term?] → docs/GLOSSARY.md (30+ terms explained)
      #v(0.3em)
      #text(weight: "bold")[Want a friendlier guide?] → SETUP-BEGINNER.md (branching, gentle)
    ]
  ]
  #v(0.5em)
  #text(size: 9pt, fill: rgb("#888"))[v1.0 unified first release]
]

#pagebreak()

= What is thiscode?

A bot-harness operations plugin that bundles Claude Code + Discord bots + Codex calls. Knowledge management and vault search are provided by the km plugin.

== The one-line differentiator

ThisCode focuses on bot operations, installation, meetings, shared memory, and model routing; the km plugin owns knowledge management and vault-search fallback.

= Install — ThisCode + the km plugin

```bash
# 1. Prerequisites (node 18+, jq, git)
# 2. ThisCode bot-harness install
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode

# 3. Install the km plugin
claude plugin marketplace add treylom/tofukyung-plugins
claude plugin install km@tofukyung-plugins

# 4. In Claude Code, configure KM storage, MCP integrations, and settings: /km:setup
#    (This command does not install the search tiers.)

# 5. Tier 4 ripgrep (local tool)
bash ~/.claude/plugins/thiscode/scripts/install-ripgrep.sh --apply

# 6. Tier 2 Obsidian CLI detection and Obsidian app guidance (optional)
bash ~/.claude/plugins/thiscode/scripts/install-obsidian-cli.sh

# 7. Tier 3 vault-search MCP (recommended)
bash ~/.claude/plugins/thiscode/scripts/install-vault-search.sh --apply

# 8. Tier 1 GraphRAG (optional; advanced)
bash ~/.claude/plugins/thiscode/scripts/install-graphrag.sh --apply

# 9. ThisCode bot-harness healthcheck
bash ~/.claude/plugins/thiscode/scripts/healthcheck.sh
```

ThisCode's scripts install the local search tools; the km plugin's `/km:search` runs the fallback. Run `/km:setup` separately in Claude Code to configure KM storage, MCP integrations, and settings.

For a branching, beginner-friendly guide: SETUP-BEGINNER.md

= 4-Tier Search

_Note: The speed, accuracy, and setup figures below are illustrative expectations
preserved from the historical ThisCode local search-tool baseline documentation,
not measurements or current km plugin runtime values. The archived
`benchmark/results/2026-05-13.json` records run metadata but, under that run's
legacy engine IDs (vault-search MCP used 2 and Obsidian CLI used 3), skips Tier 1
and Tier 2, so it does not validate the table values. The labels in the table below
follow the current km contract._

#table(
  columns: (auto, 1fr, auto, auto, auto),
  inset: 6pt,
  align: (center, left, center, center, center),
  fill: (_, row) => if row == 0 { rgb("#f0f4ff") } else { none },
  [Tier], [Tool], [Speed], [Accuracy], [Setup],
  [1], [GraphRAG (LLM + graph)], [1500-3000ms], [Very high], [25 min],
  [2], [obsidian-cli (Obsidian index)], [200-500ms], [Medium], [3 min],
  [3], [vault-search MCP (embedding)], [500-1000ms], [High], [5 min],
  [4], [ripgrep (literal)], [30-100ms], [Low], [0 min],
)

The km plugin's dispatcher tries Tier 1 → falls back to Tier 2 if results are insufficient → and so on.

= Knowledge Manager (km plugin)

Knowledge management and search are not bundled in ThisCode. Install the km plugin and use:

- `/km:search` — vault search and fallback
- `/km:knowledge-manager` — knowledge capture, classification, and storage
- `/km:setup` — create and update km plugin configuration

#pagebreak()

= LLM model routing

After search, response generation auto-selects a model based on task complexity:

#table(
  columns: (auto, auto, auto, 1fr),
  inset: 7pt,
  align: (left, center, center, left),
  fill: (_, row) => if row == 0 { rgb("#f0f4ff") } else { none },
  [Task], [Claude], [Codex], [Example],
  [Simple], [Haiku], [gpt-5.5], ["NuriFlow ARR"],
  [Medium], [Sonnet], [gpt-5.5-codex], ["Summarize the top 3 from the Q1 report"],
  [Synthesis], [Opus[1m]], [gpt-5.5-codex-spark], ["Infer the correlation between ARR and team size"],
)

`scripts/route-model.mjs` uses a heuristic (query length + keywords). User override: `--model haiku|sonnet|opus`.

= Meetings room / Codex Bridge / Shared memory / Hooks

- `/thiscode:meetings` — meeting-log folder + 4-file template, automatic
- `/codex` — bridge to OpenAI Codex (second opinion)
- shared-memory — 4-tier shared memory (T1 git / T2 machine / T3 project / T4 per-bot)
- SessionStart hook — auto-injects `soul.md`

= 5-axis Benchmark

A 5-dimension measurement — latency_ms / recall_precision / cost_tokens / setup_time_min / kg_depth.

```bash
VAULT=~/your-vault bash benchmark/runners/run-all.sh
python3 benchmark/report-generator.py --print-only
```

For measurement methodology and how to interpret: BENCHMARK.md

= FAQ + GLOSSARY references

Seven frequently asked questions: SETUP-BEGINNER.md FAQ section

Term glossary (LLM / MCP / CEL / embedding / precision / kg_depth / fallback / dispatcher / RAG, and more — 30+): GLOSSARY.md
