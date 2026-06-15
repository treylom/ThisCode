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

## 8. Code-generation minimalism gate
Before generating code, run a 6-rung ladder as a reflex (not a research project — stop at the first rung that holds):
**① Does this need to exist? (YAGNI — if speculative, skip it and say so in one line) → ② Stdlib does it? → ③ Native platform feature? → ④ Already-installed dependency? → ⑤ One line? → ⑥ Only then: the minimum that works.**
- **Lazy ≠ negligent**: trust-boundary validation, data-loss handling, security, accessibility, and verification (§3/§7) are never on the chopping block.
- Mark a deliberate simplification with a `ponytail:` comment naming its ceiling + upgrade path (e.g. `# ponytail: global lock, per-account if throughput matters`) — no silent shortcuts.
- Rung ① (YAGNI) is the key gap, complementary to §5 (verify a "broken" premise before building a workaround) and the role/autonomy boundary — it catches over-build and wrong-premise builds before the first line.
- A **review gate** (inform-the-human, not a universal mandate). Token/cost savings are conditional (on simple tasks the skill-read tax can make it *worse*) — the value is less code / fewer files and avoiding wrong builds, not guaranteed cost savings. Origin: the Ponytail ruleset (MIT, github.com/DietrichGebert/ponytail) 6-rung ladder.

▶ Fill in: where your team records deliberate simplifications and their upgrade paths.
