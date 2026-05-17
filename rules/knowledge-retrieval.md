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
