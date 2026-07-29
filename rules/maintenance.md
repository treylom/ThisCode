# Rule: periodic harness review (model-evolution drift)

Trigger: right after a major model release · ~90 days since the last review ·
any observed mismatch between what the rules/docs claim and what's actually
installed or running.

Rules get updated ad-hoc all the time, but *coherence* drifts silently without
a periodic pass — a doc that says "tool X not in use" while X is running, an
index row pointing at a renamed file, a model note three upgrades stale.

## Checklist
1. **Tool claims ↔ reality**: every tool the always-loaded docs mention (LSP,
   MCP servers, hooks, plugins) is actually installed / enabled / working —
   measure it (settings files, status commands), don't trust the doc.
2. **Old rules ↔ new model capability**: rules written for a weaker model's
   limits (small-context assumptions, forced decomposition, excessive
   confirmation) may now be capping the current model.
3. **INDEX ↔ rule files**: the trigger table and the actual rules/ directory
   are 1:1 — no dead links, no orphan files.
4. **Memory staleness**: the memory index matches the files/state it points at
   (tool paths, agent rosters especially).
5. **Live model ↔ documented model (added 2026-07-29)**: startup aliases are
   snapshots — an alias like `opus` silently follows model upgrades, so
   documents recording it miss live transitions (measured: an alias-driven
   upgrade three agents didn't know about; also the reverse — an explicit but
   stale pinned ID nobody updated, on a launcher surface nobody realized had
   diverged from the launcher actually used). Verify the *live* model (session
   transcripts record the actual model per message) against what the docs
   claim, and list **every startup surface** the model value lives on — the
   stale one is usually the surface the update routine didn't know about.
   Startup convention: explicit model IDs + one startup log line of the
   resolved model. Note the trade-off explicitly where the ID lives: an
   explicit ID gives up alias auto-upgrade, so it only stays correct if this
   periodic review actually runs. **Model *selection* stays the human's call —
   this item is bookkeeping and observation only.**

## Cadence · ownership · log
- Once after each major model release + roughly quarterly.
- Log each review (date · drift found/fixed) at the bottom of this file — an
  unlogged review didn't happen.

## On finding drift
- Fix the document (rule / index / memory / note) immediately and run the
  3-step verification from code-quality.md §3. Never leave a stale claim
  standing because "the review will catch it next quarter".

▶ Fill in: your always-loaded doc paths; every startup script/alias surface
carrying a model value; who owns the periodic schedule (a scheduler agent or a
calendar reminder).
