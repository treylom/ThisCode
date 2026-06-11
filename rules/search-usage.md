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

▶ Fill in: your KB search endpoint/skill name; your KB CLI binary; your
measured latency envelope.
