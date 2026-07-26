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

## Label discipline — the name usually dies before the value

Across a day of retractions, most of what died was the **label** — *whose value, as of when, counting what* — rather than the number itself.

> ⚠️ **Scope, corrected the next morning.** This section first read "zero wrong values; every item died at the label." Both halves were wrong. The lists were **each author's own enumeration**, not one agreed sweep — so "exhaustive" had no denominator. And wrong values did occur: a stated interval that re-measured differently, a one-digit identifier typo, and a character count that was actually bytes because the shell locale was unset. What survives is a **tendency in that sample**, not a law. Note the asymmetry — a ratio can stay true inside its own population after the generalization drawn from it is withdrawn: **a refutation reaches the generalization, not the scoped measurement underneath it.** Retract the sweep; keep the sample.

1. Claims of separation / completeness / currency / limits ("independent", "exhaustive", "current", "ceiling") must **name the axis** — an axis-less word lets one term cover both a safe axis and a dangerous one (e.g. "isolated": identity axis split, backend axis shared).
2. **Deprecate by label, not by value string.** Most prose values carry only an implicit label (position stands in for it), so deprecation is two steps: ① make the implicit label explicit (annotate as-of / ownership / status — this creates the target) ② retire that label. Parser-read fields are the exception: remove the value itself (only one role lives there).
3. Split "unknown" three ways: undetermined (measured, no rule yet) ≠ unmeasured ≠ out-of-scope (our tools cannot open it) — the axis tells the next person where to start measuring.
4. **Cite with five fields**: `metric + value + observed_at + source revision (mtime or SHA) + measurement environment`. None substitutes for another. In particular, never quote a character count from `wc -m` without declaring the locale — under a C locale it counts bytes, not characters (characters: `LC_ALL=C.UTF-8 wc -m` or a runtime's string length; bytes: `wc -c`).
5. **A correction must reach every place the value was quoted**, including derived arithmetic. Fixing only the measurement line leaves summaries and verdicts citing the old number. **Sign flips** (a dropped negation) are a separate failure mode — value and name both look intact, so no checksum, grep, or length check catches them; quote **verbatim with a source id**.

Case-based (one day's audit; the retraction lists were per-author, not exhaustive); re-judge per situation; the maintainer's call wins.
