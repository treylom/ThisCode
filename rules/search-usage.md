# Rule: KB search usage discipline (every bot — performance + latency)

Trigger: about to query the knowledge-base search (graph/semantic server or
KB CLI); a search just failed or came back empty.

> Why: 2026-06-11 GraphRAG full audit (366-query server sample) — bots
> converged on tool defaults (good), but exhibited (a) the same failed query
> re-thrown 9 times in a row with no backoff, (b) ad-hoc weight overrides that
> only polluted the cache, and (c) a stale "CLI-first" instruction still being
> injected into every bot session after the routing SoT had changed. This rule
> is the usage-side discipline; tool *selection* lives in
> [knowledge-retrieval.md](knowledge-retrieval.md) (its §1 is the SoT).

## 1. Query writing (performance)
- **3–7 word natural-language keyword queries** are the sweet spot (sample
  mean 5.3 words). Whole sentences / particle-heavy long strings degrade.
- **Trust the tool defaults** (hybrid mode, top_k, reranker on). Do not
  hand-override channel weights or modes per query — measured effect: none,
  plus cache pollution.
- Rare proper nouns / exact strings (".ai"-like tokens): on a first miss,
  retry ONCE with a spelling/alias variant — not the same string again.

## 2. Failure & retry discipline (latency)
- **Never re-throw the same query repeatedly** (regression: 9 consecutive
  identical failures). One failure/empty result = branch immediately:
  1. rephrase once (swap/trim words) →
  2. **KB CLI full-text as the 2nd-tier fallback** (unranked — widen limit,
     use isolating keywords) →
  3. plain search (grep/find).
- Server timeout / HTTP 5xx = log & report, then fall back. Do not poll the
  server waiting for recovery.
- Know the healthy latency envelope and treat exits from it as a system
  signal (report, don't retry). ▶ Fill in your measured values — e.g.
  readiness ~ms · warm search ~0.2s · cold ~1.5s · post-restart warmup ~25s.

## 3. Instruction freshness (anti-drift)
- Tool-selection SoT = knowledge-retrieval.md §1. If any memory/soul/doc
  carries a conflicting search instruction, **the SoT wins** — fix the stale
  doc in the same session you notice it (a stale instruction injected at
  session start silently mis-routes every bot).
- When search infra changes (server, channels, weights, schedule), update
  this rule's latency envelope **in the same change**.

## 4. Result-consumption contract (added 2026-07-29)
Retrieval quality and answer quality are different layers: external + local
benchmarks show recall can rise sharply while answer quality barely moves —
retrieved-but-unread evidence, evidence buried late in the prompt, and
candidate-pool inflation are consumption-layer failures no retriever tuning
fixes. This section governs what happens *after* the search returns.
- **C1 Read the top hits before claiming.** When search results back a
  factual claim, a verdict, or a deliverable, actually open and read the top
  ~3 results — never judge existence/absence/cause from titles + snippets.
  Casual reference lookups and mid-exploration probes are exempt. If the top
  hits merely repeat the same claim, keep opening further results (within the
  existing fallback chain) until a different evidence type appears. Cite only
  documents actually read.
- **C2 Front-load the evidence.** In follow-up prompts and delegation
  messages, put the load-bearing evidence first (`doc — 1-line finding —
  1-line relation`), supporting material after. Do not repeat the same
  evidence in body + appendix + summary. (Positional-decay numbers are
  single-dataset, single-model findings — treat as direction, not a fixed
  threshold.)
- **C3 Widen top_k only to verify absence.** Do not raise top_k hoping for
  better answers (measured: pool inflation pushes gold hits *out*). Widen
  only when you must check that something is truly absent, and label those
  results "boundary check", separate from top evidence.
- **C4 Multi-doc handoffs carry a relation line.** Passing 3+ documents to
  another agent/prompt: one line stating how they relate (e.g. `A=root-cause
  measurement · B=our repro · C=operating rule`). Never serialize a whole
  graph.
- Effect of C1–C4 is not yet measured here — treat as operating discipline,
  not a new hard gate; situational judgment and the user's call win.

▶ Fill in: your KB search endpoint/skill name; your KB CLI binary; your
measured latency envelope.
