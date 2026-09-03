# Rule: source discipline · verification

Trigger: about to assert a fact / proper noun / system state; about to say
"it's empty / missing / exists"; before acking a sub-agent's report.

## 1. Source discipline (hard rule)
- No source → no assertion. For factual claims, attach the path, URL, message
  ID, command output, or other checkable evidence.
- Do not format reports with fixed report labels by default. Write plainly,
  and separate confirmed facts from interpretation in normal prose.
- Gloss hard English or abbreviations on first use, for example
  `thread/inject_items` = a Codex app-server API that injects a message into a
  session log so another client can attach cleanly.
- **Carry an `origin` tag alongside quoted measurements** — `origin =
  internal_measurement | external_primary | external_secondary`. Origin is
  orthogonal to the claim's *role* (fact / inference / uncertainty /
  delegated): an external primary source can ground a fact, and your own
  measurement can stay uncertain — so never treat origin as another role.
  Why: a team's own benchmark result was once quoted in its rules as
  "(external: …)", and every agent on that team then read the team's own scorecard as
  someone else's benchmark. A dedicated origin slot blocks that relabeling
  structurally. Case-based; re-judge per situation.

## 2. No single-grep trap
- Do not stop at one grep. Cross-check: the topic's hub/index + the relevant
  folder in full + OCR'd / ambiguous proper nouns. Search the whole folder
  before declaring "empty/missing".
- Do not treat a token-optimizer-filtered `ls`/`grep` as ground truth — it can
  false-report a non-empty dir as empty. For debugging / forensic / secret
  scans, use a raw (unfiltered) path or a dedicated tool, not the filtered one.
  This applies to sub-agent greps too — re-verify their "CLEAN" yourself.
- Do not conclude a tool/feature "can't do X" from a limited probe (small
  limit, single sample, default params). A missing result under a tight
  limit can be ranking-burial, not absence. Before asserting absence:
  **expand the boundary** (max out limit/range/depth — does it appear?)
  and **isolate the feature** (probe with input that exercises only that
  capability). Limited-observation absence claims are the single-grep
  trap in another form.

## 3. Sub-agent report verification (hard rule)
- Before acking a subordinate report: self-identify, verify the file-system
  fact, and cross-check. Assume a same-account multi-instance is possible.

## 4. No name hallucination
- When mentioning another bot/agent, never generate the name. Keep a fixed
  roster; cross-check the roster source before mentioning.

## 5. Ambiguous commission-target gate (conditional)
- When a commission's target name can map to **multiple system entities**
  (same-named repos, a skill vs. the plugin that ships it, multi-layer deploy
  surfaces) AND the work **mutates state or acts publicly**, confirm one
  canonical `TARGET: <path/repo>` line before starting — either re-ask the
  user, or state your resolved interpretation after checking the real system.
- Single-entity targets and read-only work are exempt (don't over-harden).
  Origin: an orchestrator misread "the X plugin" three layers deep (internal
  lab → bundled skill → public marketplace) and needed two user corrections.

▶ Fill in: your roster/source-of-truth paths; your token-optimizer's raw-bypass
command; per-topic hub/index locations to cross-check.

## 6. Label discipline — usually it's the name that dies, not the value

Across a day of retractions, most of what died was the **label** — *whose value, as of when, counting what* — rather than the number itself.

> ⚠️ **Scope correction — the next morning.** This section first read "zero wrong values; every item died at the label." Both halves were wrong. The lists were **each author's own enumeration**, not one agreed sweep — so "exhaustive" had no denominator. And wrong values did occur: an interval stated as 40 minutes that measured 27:51 on re-check, a one-digit identifier typo, and a character count that was actually bytes because the shell locale was unset. What survives is a **tendency in that sample**, not a law. Note the asymmetry — a ratio can stay true inside its own population after the generalization drawn from it is withdrawn: **a refutation reaches the generalization, not the scoped measurement it rests on.** Retract the sweep; keep the sample.

1. Claims of separation / completeness / currency / limits ("independent", "exhaustive", "current", "ceiling") must **name the axis** — an axis-less word lets one term cover both a safe axis and a dangerous one (e.g. "isolated": identity axis split, backend axis shared).
2. **Deprecate by label, not by value string.** Most prose values carry only an implicit label (position stands in for it), so deprecation is two steps: ① make the implicit label explicit (annotate as-of / ownership / status — this creates the target) ② retire that label. Parser-read fields are the exception: remove the value itself (only one role lives there).
3. Split "unknown" three ways: undetermined (measured, no rule yet) ≠ unmeasured ≠ out-of-scope (our tools cannot open it) — the axis tells the next person where to start measuring.
4. **Cite with six fields**: `target_path + metric + value + observed_at + content_revision (mtime or SHA) + environment (locale etc.)`. None substitutes for another; quoted measurements additionally carry `+ origin` (§1). (The earlier five-field form — no `target_path`, "source revision" — is historical; do not use it for new citations.) Values merged from several sources additionally carry `+ source + aggregation_rule`; history/attribution claims carry `+ provenance_role + introducing_commit + author` — these are separate contracts, not one slot. In particular, never quote a character count from `wc -m` without declaring the locale — under a C locale it counts bytes, not characters (characters: `LC_ALL=C.UTF-8 wc -m` or a runtime's string length; bytes: `wc -c`).
5. **A correction must reach every place the value was quoted**, including derived arithmetic. Fixing only the measurement line leaves summaries and verdicts citing the old number. **Sign flips** (a dropped negation) are a separate failure mode — value and name both look intact, so no checksum, grep, or length check catches them; quote **verbatim with a source id**.
6. **Attribute work or a change only with a field that can answer “who.”** File `mtime` answers **when**, not who. For committed work, use the introducing commit and author; while work is uncommitted, ask the author or check **every** plausible active session. If neither is available, label the author `unknown` rather than inventing one. Checking only yourself among N candidates proves at most your own alibi. Runtime/process ownership and work ownership are separate questions, and automated output may have no human/agent owner. The speaker records the attribution ruler immediately before making the claim. Case-scoped to an uncommitted-change misattribution; re-judge per situation; the maintainer's call wins.

Case-based (one day's audit; the retraction lists were per-author, not exhaustive); re-judge per situation; the maintainer's call wins.

## 7. Counting discipline — confirm counts through a second measurement layer

1. Before a count is used in a claim, judgment, or deliverable — **and before it
   is retracted, corrected, or restored** — confirm it via a second path whose
   *measurement layer* differs (inside vs outside a tool wrapper, a different
   process boundary). Two syntaxes through the same layer (e.g. two glob
   spellings into the same tool) are not a second path. Rationale: retractions,
   prescriptions, and recovery edits are themselves measurements, and teams
   that gate the original count routinely leave the follow-ups ungated.
2. **Resolve the executable name once** (`type -a <cmd>` / `which <cmd>`) for
   non-trivial counts or absence judgments: shell shims can bind a familiar
   name (e.g. `grep`) to a different binary with silent filters — ignore-file
   lists that drop allowlisted trees, or binary-skip flags that drop any file
   containing a stray NUL or invalid-UTF-8 byte. Prefer a known-clean binary
   (`command grep`, an absolute path) and record the resolution with the value.
3. **Aggregation prints per-item lines, not just totals** — a total that hides
   its items cannot show where it went wrong. Aggregated values carry their
   `aggregation_rule` (which cells count, keyed how); without it, a correct
   table still double-counts on re-derivation.
4. **Detectors can die silently — ship every check with a positive control.**
   Seed a known defect once and confirm the check catches it before trusting
   its zero (an empty-pattern grep returns line counts, not NUL counts). An
   inclusion invariant (whole ≥ sum of parts) catches partial observation, and
   a violated invariant means the *instrument* is broken: adopt neither value;
   re-measure through an independent path.

5. **Hook-block counts in Claude Code transcripts anchor on `"type":"hook_blocking_error"`.** The keys `"permissionDecision":"deny"` and `"decision":"block"` occur **zero** times across transcripts, so counting on them reports a false "0 blocks". Attribute per hook through the `hookEvent` / `blockingError` labels on the same record (census finding, 2026-09-02).


## 8. Checker discipline — pass messages, signal placement, transcription

When building a checker (health check, gate, counter, verification script) or
consuming its output:

1. **Two lines in every pass message**: "what question this check answers" +
   "what the answer was compared against". An enumeration only gives you places
   to look; the verdict comes from comparing against the canonical source.
   Count-based passes ("N or more = ok") are out — use a named expectation set
   plus canonical comparison.
2. **Signal placement**: never mix warnings or incomplete-work signals into the
   body of a success message — separate line, separate label, or promote to
   exit status. **"Quantity 0" must not print as a pass** (`injected 0`,
   `matched 0` = a failure wearing a success sentence), and a plausible-looking
   substitute value is a warning too (a likely number ≠ a measured number).
   Three shapes of "failure printed as success": warnings inline, zero/no
   wearing a value's face, exit-code vs body divergence (a wrapper's exit code
   must feed the failure tally).
3. **Transcription audit**: any number copied between tables gets a column-sum
   check against its origin — transcription is unchecked replication
   (double-count incidents occur on both the submitting and the aggregating
   side). When a transcript is the measuring stick, design out
   **self-reference contamination** (the act of measuring appearing inside the
   thing being measured).
4. Checker survival = built-in positive *and* negative controls, and **the kind
   of decoy determines the kind of defect you can detect** — decoys that only
   vary identifiers will not catch phrasing-level blind spots (in one live day,
   five checker deaths — four caught by positive controls, one by "the number
   looked like an answer" suspicion of an empty-pattern OR matching every
   line. Positive controls are necessary, not sufficient).

## 9. Live counts run as positive–negative pairs — decoy inside the very command (2026-08-08)

- §8 covers building a checker; this covers **every ad-hoc count or absence
  claim you make in daily work**. Run it as a pair: plant a decoy you *know*
  exists (positive) and one you know doesn't (negative) **inside the same
  command that produces the count** — a separate verification call splits the
  measurement into two layers, and the person running it cannot feel the split.
  (Observed: the same log counted 4 with a loose pattern and 3 with a
  line-structure anchor — the discrepancy was only visible because the decoy
  rode in the same command.)
- Speak the count with its control attached: "N items (decoy 2/2 caught)" — by
  the agent making the claim, in that same message. A count arriving without its
  ruler invites the reader to trust a number nobody proved alive.
- **The decoy has its own ruler (2026-09-01, 6 recurrences in one corpus)**: for
  absence/count verdicts never use bare `wc -l` — count the pattern itself
  (`grep -c '^pattern'`) and keep **one role per flag** (`-l`+`-c` style
  conflicts pick one output silently: an expected 0 came back as 589). And write
  the **expected value next to the decoy before running it** — pre-stated
  expectation is an independent verification axis beyond self-checks and
  cross-review; in all six failures it was the only thing that caught the break.
- **Declaring a gate/status label requires one live measurement of its target
  (2026-09-01)**: "consensus is not measurement" — three agents chorused a
  "still RED" label that had been false for four months.
- Rule layer, not a hook: a machine cannot see whether you planted a decoy, and
  forcing a self-declared checkbox recreates the empty-slot disease (§ owner-slot
  rule in skill-process). Not habit layer either — this one was already tried as
  a habit and re-occurred the next day; "your own ruler is invisible to you" is
  structural.

Case-based (2026-08-05 40-case census); re-judge per situation; the
maintainer's call wins.
