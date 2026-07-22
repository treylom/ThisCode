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
