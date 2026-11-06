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

## 1.5 Two-store routing — conversation memory vs curated KB (added 2026-07-29)
If the deployment has BOTH a conversation-memory store (indexed past
sessions/decisions) and a curated KB (notes/docs/graph), split by what the
question asks *before* picking a tool:
- **Past conversations, who said what, decision provenance, prior-failure
  precedent → conversation-memory store first.**
- **Current canonical docs, concepts, maps-of-content, relations → ranked
  KB search first.**
- **Mixed questions → query both**, then: current norms/state/wording
  prefer the canonical doc; who/when/why-decided prefers the original
  conversation; if they disagree, surface the conflict as `current canon`
  vs `historical provenance` — never silently merge.
- **Never widen one store's no-hit into "absent everywhere"** — the other
  corpus may hold it.
- Marker integration: list only the stores actually queried in the
  attestation marker's `targets=` (§2).

▶ Fill in: your KB CLI binary + path; your graph/semantic search skill
name; which stores count as "our docs" vs plain code; your
conversation-memory store name (if any) for §1.5 routing.

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

- **Evidence goes into the knowledge base before you write (operator directive, 2026-11-01).** Pages and files the user hands you, and outside material you collect for a task (captures, documents, links), are saved into the KB *before* you write the deliverable; when you write, reopen the saved copies through KB search. Collecting them only in a task's scratch folder is not enough (a past task left 73 captures stranded in a work folder). No mechanical gate yet — a written discipline.

▶ Fill in: your memory/KB search command; your shared-vs-local memory split;
the exact store names your marker's `targets=` should list.

## 2.5 Injection is not lookup — two different layers (added 2026-08-02)
If the deployment auto-injects "relevant past decisions" into each prompt
(a conversation-memory injector), treat the injected block as a **hint**,
not as a lookup:
- Do not make factual claims / verdicts from injected content alone --
  run one canonical lookup first (same axis as the answer-time
  verification gate in source-fact.md).
- When injected content and a fresh lookup disagree, **the lookup wins**:
  injection is a snapshot, the canon is current.
- Extend the §2 marker with `injected=yes|no` so a later audit can tell
  "injection present but unread" from "no injection at all".
- If injections run empty for days, that is not "no memories" -- **the
  injector may be dead**; check its error log once.
- Detector-side corollary: any compliance detector counting §2 markers
  must scan only the agent's own output for that turn and exclude
  injected / rule-file text -- otherwise the marker template that rules
  and injectors themselves carry counts as compliance (a detector that
  can never fail, i.e. fail-never).
Case-based (dual-injection-surface incident, 2026-08-02); situational
judgment; the user's call wins.

▶ Fill in: your injector's name + its error-log path.

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

## 4. Web research — open pages with your own tools first; the browser agent only where they fail (operator directive, 2026-10-26)

When research or search needs a web page opened or a video downloaded, use the agent's own tools first (web search, URL fetch, the research skill's page-opening steps, a media download tool). Hand a page to the browser agent (a tool that drives a real, logged-in browser for you) only when those tools cannot open it (login wall, script-only render, blocked fetch).
- In that fallback the browser agent may run the job on its own; if your setup normally asks the user which browser-control mode to use, research fallback skips that question.
- Acting on a site is not research: logging in, signing up, account or console settings, OAuth, token reissue, filling a shared sheet or form — these keep going through the browser agent as before (how to drive it: see the 2026-11-02 update below).
- Write the condition by purpose (reading for research vs acting on a site), not by tool name, so swapping in a different fetch tool cannot sidestep it.
- Background: a research agent asked how to use the browser agent for page opening and video downloads; the operator answered that the browser agent is only for places that will not open.
- **Update (operator directive, 2026-11-02) — never ask which browser-control mode to use.** Whenever site work needs the browser agent (research fallback or acting on a site), do not ask the user how to drive it. Order: ① hand the job to the browser agent's autonomous mode; ② if that agent cannot run because it has no usage left (quota, limit or credit exhausted), tell the user in one line what you were trying to do and that usage ran out; ③ if it has usage but gets stuck (cannot find the screen, repeats the same step, gives a wrong result), drive the browser yourself through its interactive mode. Questions about *what* to do — account, payment, deletion — are still the user's decision and are still asked. The older "ask which mode" wording in this section is kept as history and is replaced by this order.
- Background: the user found per-task "which mode?" questions too tiring and set this order for every agent.

▶ Fill in: your page-fetch and download tools; your browser-agent tool and its autonomous / interactive modes.
