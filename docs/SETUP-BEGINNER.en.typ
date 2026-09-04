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
  #text(size: 26pt, weight: "bold")[thiscode — Easiest Setup Guide]
  #v(0.5em)
  #text(size: 16pt, fill: rgb("#555"))[Even first-time users finish in 5 steps]
  #v(2em)
  #box(fill: rgb("#f0f4ff"), inset: 14pt, radius: 6pt, width: 80%)[
    #align(left)[
      #text(weight: "bold")[Who this guide is for]
      #v(0.3em)
      OK even if you've barely used a terminal. Copy + paste + Enter, one line at a time.
      #v(0.5em)
      #text(weight: "bold")[What you need]
      #v(0.3em)
      - An internet-connected computer (Mac / Linux / WSL — Windows native to come later)
      - Claude Code (install from https://claude.com/code)
      - 5\~30 minutes (depending on the Tier you pick)
    ]
  ]
  #v(1em)
  #text(size: 10pt, fill: rgb("#888"))[Written 2026-05-13 | v1.0]
]

#pagebreak()

= Before You Begin — The Whole Flow at a Glance

In one line, the flow looks like this:

#v(0.3em)
#box(fill: rgb("#fffaf0"), inset: 10pt, radius: 4pt, width: 100%)[
  #text(weight: "bold")[0. Environment check] $arrow$ #text(weight: "bold")[1. Plugin install] $arrow$ #text(weight: "bold")[2. Search MCP] $arrow$ #text(weight: "bold")[3. Obsidian branch] $arrow$ #text(weight: "bold")[4. GraphRAG (optional)] $arrow$ #text(weight: "bold")[5. Healthcheck]
]

#v(0.5em)

Each step ends with a #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ This is what success looks like] checkpoint. If it fails, stop at that step — don't move on.

#v(0.5em)

== What is 4-Tier search?

The heart of thiscode is that search falls back across 4 tiers — if a faster tool can't find the answer, it escalates to a more accurate one.

#box(fill: rgb("#f8f9fa"), inset: 10pt, radius: 4pt, width: 100%)[
  - #text(weight: "bold")[Tier 4 — ripgrep] (default, 0-min setup) — literal string match, very fast
  - #text(weight: "bold")[Tier 3 — obsidian-cli] (3-min setup, Obsidian users only) — uses Obsidian's index
  - #text(weight: "bold")[Tier 2 — vault-search MCP] (5-min setup) — embedding-based semantic search
  - #text(weight: "bold")[Tier 1 — GraphRAG] (25-min setup, advanced) — LLM + graph, the most accurate
]

#v(0.5em)

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[Tip] — For the fastest start, just Tier 4 + 3 (path 3-A) is enough. Try GraphRAG (path 4-C) once you're comfortable.
]

#pagebreak()

= Step 0 — Wizard entry (recommended in v2.1)

The easiest path is the `thiscode init` wizard — it auto-detects vault / tools / resources and recommends 8 phases.

```bash
bash ~/.claude/plugins/thiscode/scripts/claude-discode-init.sh
```

What the wizard asks:
- Which Tier's search tool should I install?
- Install GraphRAG? (recommended for 500+ notes — optional anytime)
- Mode R preflight? (recommended for 2000+ notes, read-only)

For step-by-step manual installation, see steps 1\~5 below (for users who don't go through the wizard).

#pagebreak()

= Step 0 — Environment check (2 min)

First check what is already installed. Open a terminal (Mac = Spotlight `cmd+space` → search "Terminal" / WSL = the Ubuntu app / Linux = Ctrl+Alt+T) and copy + paste + Enter, one line at a time.

#v(0.5em)

== 0-1. Check Node.js

```bash
node --version
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ Success looks like] — a number such as `v18.17.0` is fine
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ If it fails] — if you see "command not found", install the LTS version (v18 or v20) from https://nodejs.org and restart your terminal
]

#v(0.5em)

== 0-2. Check jq

```bash
jq --version
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ Success looks like] — output like `jq-1.6`
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ If it fails] — Mac: `brew install jq` / Ubuntu / WSL: `sudo apt install jq`
]

#v(0.5em)

== 0-3. Check git

```bash
git --version
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ Success looks like] — `git version 2.x.x`
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ If it fails] — Mac: `xcode-select --install` / Ubuntu / WSL: `sudo apt install git`
]

#pagebreak()

= Step 1 — Plugin install (2 min)

```bash
mkdir -p ~/.claude/plugins
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode
```

#v(0.3em)

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ Success looks like]
  ```
  Cloning into '/Users/.../thiscode'...
  remote: Enumerating objects: ...
  Receiving objects: 100% (...), done.
  ```
]

#v(0.3em)

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ If it fails]
  - "Permission denied" → check write permission for `mkdir ~/.claude/plugins`
  - "already exists" → already installed. Update with `cd ~/.claude/plugins/thiscode && git pull`
]

= Step 2 — Search MCP install (5 min, recommended)

```bash
bash ~/.claude/plugins/thiscode/scripts/install-vault-search.sh --apply
claude mcp list | grep vault-search
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ Success looks like] — a single `vault-search` line in the output
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ If it fails]
  - `claude: command not found` $arrow$ Claude Code is not installed. https://claude.com/code
  - npm install fails $arrow$ try `nvm use 18` or `nvm install 18`
]

#box(fill: rgb("#fff8e1"), inset: 10pt, radius: 4pt)[
  #text(weight: "bold")[Important] — Restart Claude Code once after install (`exit` then relaunch).
]

= Step 3 — Do you use Obsidian? 🤔

#box(fill: rgb("#fff8e1"), inset: 12pt, radius: 6pt, width: 100%)[
  #text(weight: "bold")[Yes] $arrow$ 3-A (Install Obsidian CLI, 3 min)
  #v(0.3em)
  #text(weight: "bold")[No] $arrow$ 3-B (Skip, go straight to Step 4)
]

== 3-A. Install Obsidian CLI (Obsidian users only)

```bash
bash ~/.claude/plugins/thiscode/scripts/install-obsidian-cli.sh
which obsidian-cli
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ Success looks like] — a path such as `/usr/local/bin/obsidian-cli`
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ If it fails] — add `sudo`, or see the manual-install section in the README
]

== 3-B. Skip — it still works without Obsidian ✅

- Only Tier 3 (Obsidian CLI) is skipped among the 4 tiers
- Tiers 1 / 2 / 4 still run normally — about 80% of the functionality remains
- Move on directly to Step 4

#pagebreak()

= Step 4 — Going all the way to GraphRAG? 🚀

Pick one of three options:

#table(
  columns: (auto, 1fr, auto),
  inset: 8pt,
  align: (left, left, center),
  fill: (_, row) => if row == 0 { rgb("#f0f4ff") } else { none },
  [#text(weight: "bold")[Choice]], [#text(weight: "bold")[Who?]], [#text(weight: "bold")[Time]],
  [4-A], [Skip for now, get started fast (up to Tier 3)], [0 min],
  [4-B], [Docker-comfortable user], [10 min],
  [4-C], [Want local Python + direct debugging], [25 min],
)

== 4-A. Skip for now ✅

$arrow$ Jump straight to Step 5

== 4-B. Easy install via Docker

```bash
docker --version
docker pull ghcr.io/treylom/ThisCode-graphrag:v1.0
docker run -d -p 8400:8400 -v ~/vault:/vault \
  --name thiscode-graphrag \
  ghcr.io/treylom/ThisCode-graphrag:v1.0
curl localhost:8400/health
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ Success looks like] — `{"status":"ok"}`
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ If it fails]
  - Docker not installed $arrow$ https://docs.docker.com/get-docker/
  - Port 8400 conflict $arrow$ switch to `-p 8401:8400` and set env `GRAPHRAG_URL=http://localhost:8401`
]

== 4-C. Local Python install

```bash
python3 --version
bash ~/.claude/plugins/thiscode/scripts/install-graphrag.sh --apply
curl localhost:8400/health
```

Install time 5\~10 min + initial indexing 15 min = about 25 min total.

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ Success looks like] — `{"status":"ok"}`
]

#pagebreak()

= Step 5 — Verify everything's OK 🎉

```bash
bash ~/.claude/plugins/thiscode/scripts/healthcheck.sh
```

#box(fill: rgb("#e8f5e9"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#2c8a3d"))[✓ Success looks like — SKIP markers reflect your choices]
  ```
  thiscode healthcheck v1.0
  ─────────────────────────────────
  ✓ Tier 4 (ripgrep)  : OK
  ✓ Tier 2 (MCP)      : OK
  ○ Tier 3 (CLI)      : SKIP (no Obsidian — chose 3-B)
  ○ Tier 1 (GraphRAG) : SKIP (chose 4-A)
  ─────────────────────────────────
  all required checks passed ✅
  ```
]

#box(fill: rgb("#fde8e8"), inset: 8pt, radius: 4pt)[
  #text(weight: "bold", fill: rgb("#c53030"))[❌ If it fails]
  ```bash
  cat ~/.thiscode-setup.log
  ```
  Copy this file's contents into a GitHub Issue:
  https://github.com/treylom/ThisCode/issues/new?template=setup-failure.yml
]

= Try it out

Inside Claude Code:

```
/thiscode:help
```

For vault search, install the km plugin first:

```
claude plugin marketplace add treylom/tofukyung-plugins
claude plugin install km@tofukyung-plugins
/km:search "hello first search"
```

Congratulations! 🎉

#pagebreak()

= Frequently Asked Questions

== Q1. Can I stop in the middle of setup?

Yes. Each step is independent, so even just steps 1-3 give you working Tier 4 (ripgrep) search.

== Q2. macOS / Linux / Windows / WSL — all supported?

macOS / Linux / WSL are verified. Windows native is on the roadmap (WSL recommended for now).

== Q3. I'm a student — what about cost?

- Tier 4 (ripgrep) + Tier 3 (Obsidian) = 100% free
- Tier 2 (MCP) = free (inside your Claude Code subscription)
- Tier 1 (GraphRAG) = OpenAI / Anthropic API calls → roughly \$0.5\~5 for an initial indexing, depending on vault size

== Q4. I already use just obsidian-cli — what's the difference?

See the 5-axis benchmark in the README:
- Tier 1 GraphRAG = recall +44% over Tier 2 obsidian-cli alone
- But 25-min setup + LLM cost

== Q5. Where do I leave feedback?

GitHub Discussions Feedback category: https://github.com/treylom/ThisCode/discussions/categories/feedback

A 5-question schema, ~2 minutes to answer → it feeds into the v1.1 graduate decision.

#v(2em)

#align(center)[
  #box(fill: rgb("#f0f4ff"), inset: 14pt, radius: 6pt, width: 70%)[
    #text(weight: "bold")[Need more help?]
    #v(0.5em)
    - GitHub Issues: https://github.com/treylom/ThisCode/issues
    - Community: GitHub Discussions
    - Docs: SETUP.md (for developers) / AGENTS.md (Custom Hybrid v1.0 spec) / BENCHMARK.md (interpreting the 5 axes)
  ]
]
