# Rule: SOURCE FACT · verification discipline

Trigger: about to assert a fact / proper noun / system state; about to say
"it's empty / missing / exists"; before acking a sub-agent's report.

## 1. 4-way label (hard rule)
- Every claim carries a label: **SOURCE FACT / DERIVED INFERENCE /
  UNCERTAINTY / DELEGATED TASK**. No source → no assertion.
- Keep the four label names, but write the content in plain language for
  user-facing reports. Gloss hard English or abbreviations on first use, for
  example `thread/inject_items` = a Codex app-server API that injects a message
  into a session log so another client can attach cleanly.

## 2. No single-grep trap
- When labeling SOURCE FACT, do not stop at one grep. Cross-check: the topic's
  hub/index + the relevant folder in full + OCR'd / ambiguous proper nouns.
  Search the whole folder before declaring "empty/missing".
- Do not treat a token-optimizer-filtered `ls`/`grep` as ground truth — it can
  false-report a non-empty dir as empty. For debugging / forensic / secret
  scans, use a raw (unfiltered) path or a dedicated tool, not the filtered one.
  This applies to sub-agent greps too — re-verify their "CLEAN" yourself.

## 3. Sub-agent report verification (hard rule)
- Before acking a subordinate report: self-identify, verify the file-system
  fact, and cross-check. Assume a same-account multi-instance is possible.

## 4. No name hallucination
- When mentioning another bot/agent, never generate the name. Keep a fixed
  roster; cross-check the roster source before mentioning.

▶ Fill in: your roster/source-of-truth paths; your token-optimizer's raw-bypass
command; per-topic hub/index locations to cross-check.
