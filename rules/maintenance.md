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
   Compare the surfaces **mechanically** (a diff/sweep command), not by eye —
   a value that *looks* explicit can still be wrong (measured: an eyeball pass
   would have accepted a freshly-pinned-but-stale ID that the mechanical
   comparison caught). Record the model ID **separately from launcher flags**
   — a context-window or effort flag appended to the launch argument is not
   part of the model ID, and transcripts report the bare ID.
   Startup convention: explicit model IDs + one startup log line of the
   resolved model. Note the trade-off explicitly where the ID lives: an
   explicit ID gives up alias auto-upgrade, so it only stays correct if this
   periodic review actually runs. **Model *selection* stays the human's call —
   this item is bookkeeping and observation only.**

6. **Skill vs sub-agent scope precedence (they resolve in opposite
   directions)**: when the same name exists in personal (`~/.claude/`) and
   project (`.claude/`) scope, the two systems disagree — skills resolve
   `enterprise > personal > project` (**personal wins**); sub-agents resolve
   `managed > CLI flag > project > user > plugin` (**project wins**). Nested
   collisions differ again, and the difference is naming rather than priority:
   the bare name always resolves to the project-root skill, and a nested
   same-named skill is reachable *only* by its directory-qualified name — there
   is no way to select it by the short name at all. That qualified name is not
   listed until something in that directory has been touched, so "the skill
   isn't there" can mean *not yet exposed* rather than *absent* — worth knowing
   before concluding a skill is missing. For sub-agents the definition closest
   to the working directory wins outright and the others disappear. Newer CLI
   versions inject a mitigation notice next to the skill list telling you to
   invoke the qualified variant instead — **do not count that notice as a
   defense**: it appears only from CLI `v2.1.203` onward (older versions get
   nothing at all), and it is phrased as an instruction to act, so a session
   may flag it as prompt-injection and refuse it. A notice that has to be
   obeyed is not a mechanism. (measured: a fixture under a nested directory,
   comparing the skill list and short-name invocation before and after
   touching a file in it)
   - **The dangerous direction is skills.** Project-scope rule skills are
     silently overridden by a same-named personal skill — no warning, no
     error, no log line. A rule set that lives in project scope can be
     disabled by one file in a personal folder.
   - Run the check with a **positive control built in**: if either side counts
     zero, the script must report *check failed*, not *no collisions*. Its exit
     codes are `0` clean · `1` collision found · `2` check broken — a detector
     that finds something must be able to say so in its exit status, or a hook
     passes silently. The code is a signal, not a policy: whether a `1` blocks
     anything is the caller's decision, not the script's.
     A broken path must never read as a clean bill of health.
   - Read a zero result as "no duplicate names right now", **not** "the design
     prevents duplicates". If the only reason a system is safe is that nobody
     happened to reuse a name, that is luck, not a defense.
   - Structural fix worth considering: give rule skills a plugin namespace
     (`plugin:skill`), which the documentation states cannot collide across
     levels.

7. **Core→full-text pointer traversal (relational check)**: verify that every full-text rule file referenced by a core rule file actually exists, by traversing the pointers — never by comparing against a hardcoded count ("18/18"), which goes stale in both directions as files are added or removed. The only question: "does everything the core points at exist?"
   - Check: `for c in rules/*.md; do for t in $(grep -o 'rules-full/[a-z-]*\.md' "$c" | sort -u); do [ -f "$t" ] || echo "MISSING: $c -> $t"; done; done` (adjust glob/paths to the repo's actual layout — verify the pattern matches at least one real pointer before trusting a zero).
   - **Absent decoy required**: run the same expression against one pointer known not to exist and confirm MISSING fires — a zero output must be provable as "no gaps", not "check never ran".
   - The failure class concentrates in derived machines (stale clones, stash conflicts, partial checkouts), not the primary — check this axis first on secondary machines and deployments.

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
