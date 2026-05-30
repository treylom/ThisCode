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
▶ Fill in: your memory/KB search command; your shared-vs-local memory split.
