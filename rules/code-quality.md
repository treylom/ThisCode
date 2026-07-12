# Rule: Code quality · regression prevention · debug artifacts

Trigger: receiving a bug report, about to modify a file, about to claim "fixed/done", after resolving a non-trivial bug.

## 1. Prove It
- Bug report → **reproduce → fix → prove**, in that order. No speculative patching ("I think this fixes it" = failure mode).
- No root cause identified = no fix. Can't reproduce = gather more data, don't guess. Never apply a phantom fix to a file you haven't verified exists.

## 2. Before modifying a file
- List what currently works → analyze blast radius → modify → verify. Write down what could break *before* touching it.

## 3. 3-step verification after a change
1. Checklist — only the intended change went in
2. Run test — the changed feature works
3. Integration test — adjacent features didn't regress
- Never say "done" without verification.

## 4. Don't conclude absence from limited observation
- Never assert "tool/feature/field doesn't exist / can't do X" from a small-limit, single-sample, default-parameter observation.
- **Boundary**: push limit/range/timeout/depth to max — if results change it was a cutoff/ranking issue, not absence.
- **Isolation**: re-test with input that isolates exactly the capability in question.
- When checking "is it empty", scan **all file types** (`find -type f`), not just one extension — a `*.md` filter hides strays.

## 5. Verify the "it's broken" premise before building a workaround
Before building a tool/daemon/workaround on the belief that an external tool is broken: (a) measure in *your* environment/version, (b) read the official docs directly for a control lever, (c) don't rely on bug trackers alone (they collect failures, not the working pattern). A wrong premise turns into a whole wasted build.

## 6. Debug artifact contract (after fixing a non-trivial bug)
Leave a debug artifact with **fixed sections, fixed order** (don't end at "fix commit + one progress line"):
① Problem (symptom·repro) → ② Hypotheses (**≥3, on different axes** — environment/dependency/state/control-flow) → ③ Investigation (evidence accepting/rejecting each) → ④ Root Cause → ⑤ **Detection Gap** (why existing tests/hooks/checks missed it) → ⑥ **Sibling Search, 4 axes** (same file / adjacent module / same design decision / same symptom elsewhere — report each axis, "skipped" ❌) → ⑦ Prevention (which test/hook/rule now blocks recurrence).
- **Trivial escape hatch**: typo/config-slip class bugs skip the full artifact, but must declare `n/a — trivial fix` explicitly (silent omission ❌). Trivial = root cause 1-hop obvious AND sibling probability structurally zero.
- §6 is the *post-fix* counterpart of §1 (Prove It = before, artifact = after: knowledge asset).

## 7. Verification ladder — state WHICH grade your "verified" means
"GREEN / verified / passed" claims must state the verification grade. Different agents mean different things by "verified" — naming the grade closes that gap (e.g. a doc *claiming* an artifact exists vs. the artifact actually existing).
- **Ladder (low → high)**: ① **deterministic** — automated checks / script asserts (seconds) → ② **scenario replay** — real-scenario reproduction / e2e round-trip (minutes) → ③ **evaluator** — independent evaluator / cross-engine review → ④ **human review**.
- A GREEN that only passed a lower rung must say so (e.g. "GREEN — ① deterministic only"). **No silent downgrade** — never substitute a lower rung where a higher one was required. Executable proof > eyeballing code.
- **JSON form**: new automation outputs carry `schema_version` + `proof_class` (e.g. fixture-smoke / in-process / live). Retrofit existing outputs only on next touch — no bulk backfill.
- §3 says *what* to verify; §7 names *at which grade* you verified it.
- **Validity threats + benchmark fixture convention**: ① **Threats to validity** — a non-trivial verification / experiment / benchmark conclusion carries an explicit list of "why you might *not* trust this result" (sample size, measurement scope, generalization limits, n=1 noise) as named items, not one line of prose. ② **Benchmarks = fixtures + raw output + threats** — experiments and benchmarks use fixed fixtures (deterministic inputs) + preserved raw output (e.g. JSON) + a threats note, so they reproduce. Both are a lightweight extension of the §7 ladder (existing discipline unchanged, no new hard gate).
- **When the final judgment is human taste, measure once at n≥18 then escalate — no self-convergence loop**: for a metric whose final acceptance is a person's preference (game balance, tone, design taste), don't keep re-measuring to converge on the "right" number yourself. Measure once at n≥18 (probabilistic outcomes need n≥18 — a small sample's 0/N can be chance), then escalate the range/candidate early ("is this range OK?") and let the human make the call. If the judge is a person but the bot self-converges, that's over-verification overrun (opportunity cost — an afternoon burned on precision nobody asked for). Situational judgment; user's final call wins.

## 8. Code-generation minimalism gate
Before generating code, run a 6-rung ladder as a reflex (not a research project — stop at the first rung that holds):
**① Does this need to exist? (YAGNI — if speculative, skip it and say so in one line) → ② Stdlib does it? → ③ Native platform feature? → ④ Already-installed dependency? → ⑤ One line? → ⑥ Only then: the minimum that works.**
- **Lazy ≠ negligent**: trust-boundary validation, data-loss handling, security, accessibility, and verification (§3/§7) are never on the chopping block.
- Mark a deliberate simplification with a `ponytail:` comment naming its ceiling + upgrade path (e.g. `# ponytail: global lock, per-account if throughput matters`) — no silent shortcuts.
- Rung ① (YAGNI) is the key gap, complementary to §5 (verify a "broken" premise before building a workaround) and the role/autonomy boundary — it catches over-build and wrong-premise builds before the first line.
- A **review gate** (inform-the-human, not a universal mandate). Token/cost savings are conditional (on simple tasks the skill-read tax can make it *worse*) — the value is less code / fewer files and avoiding wrong builds, not guaranteed cost savings. Origin: the Ponytail ruleset (MIT, github.com/DietrichGebert/ponytail) 6-rung ladder.

▶ Fill in: where your team records deliberate simplifications and their upgrade paths.

## 9. Feature completion = full click-through + commissioner-intent diff + one adversarial pass (added 2026-07-05)
Before reporting a UI/feature implementation "done" (or cutting over), three axes:
1. **Full click-through**: actually walk every interaction path of the new/changed feature (each card type, button, link at least once) — a real-screen pass, separate from automated e2e.
2. **Commissioner-intent diff**: quote the original instruction → item-by-item table against actual behavior — comparing against "our own spec" ❌; compare against the commissioner's wording.
3. **One adversarial pass**: one line asking "would anything look wrong if the user clicked around?" (fix before reporting if something turns up).
- Background: an automated-e2e GREEN passed a page that rendered only the summary with the full text missing — the user's real clicks caught it. Situational judgment (non-UI / small changes) and the user's final feedback win.

### §3 reinforcement (2026-07-05)
- **Web deliverables: verify the final response, not a source grep**: judging "it's live" for a web page / external URL takes (a) the measured **final** HTTP status (after following redirects) + content-type + bytes, and (b) render-side confirmation (SSR can split strings across comment boundaries, so a contiguous-string grep can 0-hit falsely — probe with separated tokens). Grepping the source/references is only a pre-filter, never completion evidence.
- **Pipeline shells: capture the exit of the step you depend on directly**: if a later step (rotation, commit, post-send) depends on an earlier command succeeding, run that command alone and capture its exit directly (`set -o pipefail` or drop the pipe) — `$?` after `cmd | tail` is tail's exit, so failures get masked.

### §3 reinforcement (2026-07-12)
- **Never merge/pull on a dirty tree in a shared repo — merge in an isolated worktree**: git's merge *refusal* path is not read-only. On a dirty tree, merge internally snapshots your uncommitted changes (stash create); if the merge is then refused, it restores via `read-tree --reset -u HEAD` + `stash apply` — and that apply's failure is **silently ignored**, so your uncommitted work can be rolled back with no error shown. Do merges/pulls in an isolated worktree (`git worktree add --detach <dir>`), push from there, then remove it; afterwards re-measure the shared tree (`git status --short | wc -l`) instead of trusting a stale count. If work does go missing: `git fsck --dangling` → date-filter the "WIP on …" stash snapshots → recover from them.

### §4 reinforcement (2026-07-05)
- **"The file never existed" only after `git log --all`**: don't conclude that a file absent from the working tree/HEAD "never existed" — it may have landed on another branch (real case: an auto-commit hook committed docs onto a feature branch that happened to be checked out). The git flavor of boundary expansion.
