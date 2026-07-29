# Rule: knowledge-base / project-doc retrieval

Trigger: about to search the project's own knowledge base / notes / docs
(not arbitrary code, not the web).

## 1. Pick the retrieval tool by query shape — don't raw-grep first
Searching "our own docs" with a bare find/grep when a structured index
exists is a regression (the curated store has better-than-grep retrieval).
Decide by query shape:
1. **A structured KB CLI is installed → use it first** — its
   search/tags/backlink/graph commands beat raw grep on a curated store.
2. **The query is relational / multi-hop / conceptual** ("where is X
   discussed", "what connects to Y") **→ use the graph/semantic search
   skill first** (GraphRAG / vector index), not lexical grep.
3. **Neither — a plain path, a code repo, a forensic/secret scan →
   plain search** (find/grep/read; forensic/secret scans bypass any
   token-optimizer, see source-fact.md §2).
- Tool *failure* → fall back: structured CLI → its MCP/server → direct
  read/grep. Failure-fallback is a separate concept from first-choice
  selection; do not collapse the two.
- **⚠️ A substring/exact-match KB CLI with no relevance ranking is NOT
  the default for *content recall*.** Such a CLI may match across
  filename + frontmatter + body + links, yet return hits in path/name
  order with no relevance ranking — so for a common term the relevant
  doc is buried hundreds deep and looks like a MISS at any practical
  limit. That is a structural limit of the tool, not a tunable. Route
  **content/topic recall** ("find the doc *about* X") to **ranked /
  semantic search**; reserve the exact-match CLI for **known-name
  lookup, tags, backlinks, and structure queries**, where exact
  matching is its strength. Even so, keep the exact-match CLI as a
  **mandatory 2nd-tier fallback** for content recall when the ranked
  engine is unavailable (full-text, unranked — degraded but
  functional; do not drop it from the recall path).

▶ Fill in: your KB CLI binary + path; your graph/semantic search skill
name; which stores count as "our docs" vs plain code.

## 2. Active recall — search before planning, search on failure, propagate after
The knowledge base is for active recall, not just storage. Three triggers:
- **Before planning / starting a task** -> search relevant memory/KB first
  (prior art, lessons, failure patterns), then act. Skipping this is a
  classic time-sink: re-deriving what a past note already settled, or
  re-walking a path a past failure already mapped.
- **On failure mid-task** -> do not apologize or thrash; **decide**. Search
  the KB for the recurring / similar-failure lesson, then pick the next
  move from it. Repeated "sorry" is wasted motion -- replace it with
  search-then-decide.
- **After completion** -> write the lesson into memory + register it in the
  index + **propagate** (other agents' shared store + any downstream rules
  bundle).

**Attest the search with a marker.** A response that fired one of these
triggers carries one line naming what was searched:
`memory checked: <path-or-no-hit> | targets=<stores searched> | query="..."`.
**A no-hit is a success** — record it as no-hit rather than inventing a
recollection to fill the line.

Why write it down when a hook already enforces it: with enforcement but no
rule text, a fail-open miss reads as absence rather than violation — there is
nothing to compare against, so the gap is undetectable. The written rule is
what gives the check a target.

▶ Fill in: your memory/KB search command; your shared-vs-local memory split;
the exact store names your marker's `targets=` should list.

## 3. Active exploration before starting a task — three axes + peer-agent memory (added 2026-07-29)
Commissioned directly by the user after three recurring symptoms: an agent
failing to find — and then hand-rolling — what an installed tool already
provided; low-context output because
the agent never read the owner's published repos; thin expertise because the
knowledge sat in *another agent's* memory.
- **Tool sweep** — search the existing tool inventory (skills, scripts, MCP
  servers, plugins) for the tool this task needs *before* hand-rolling
  anything (complements porting-infra's "check upstream before hand-rolling").
- **Repo sweep** — read the owner's/organization's relevant repos before
  producing; don't re-invent what's already published or produce output that
  ignores it.
- **Expert agent + peer memory** — when the needed expertise lives outside
  your own memory, actively convene the domain-expert agent (a real
  meeting/consult, not a guess), and read peer agents' memory stores
  **read-only** — the domain-to-agent roster decides whose memory to consult.
Situational judgment; the user's call wins.

▶ Fill in: your tool-inventory locations; the repo namespace to sweep;
peer-agent memory paths + the roster mapping domains to agents.
