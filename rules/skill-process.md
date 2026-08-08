# Rule: skill · process discipline

Trigger: starting a build/design ("let's build X") · debug · verify task;
an automated experiment loop; delegating to a sub-agent.

## 1. Skill-invoke gate
- creative / debugging / verification / build task = invoke the relevant skill
  **before** any response or action. If there's even a 1% chance a skill
  applies, invoke it.
- Priority: process skill (brainstorming · debugging) first → implementation
  skill. Conflict: **explicit user instruction > skill > default**.
- **Commissioned tool = center of the process (no silent abandonment)**: when
  the user names a specific skill/tool in a commission, that tool anchors the
  workflow. If the output gets rejected, the first move is "use the tool
  differently" — dropping the tool is not on the menu (rejection usually
  targets the content, not the tool). If a real capability limit forces a
  switch, ask first ("tool X can't do Y — switch to Z?") instead of quietly
  swapping; and make per-step tool usage visible in plans so the user can see
  the commissioned tool at work.
- **A spec/seed pipeline needs a stated end time.** When work is commissioned
  through a structured pipeline (interview → spec → run → evaluate), write the
  cutoff into the spec. Without one, refinement becomes the goal: the loop
  keeps improving the measurement and eats the deliverable it was supposed to
  produce. Reaching the cutoff means reporting with whatever exists at that
  moment; extending it is the human's call, not the loop's. (Origin: a night
  where building an exhaustive measurement apparatus displaced the repair it
  was meant to serve, and took three human interventions to redirect.)
- **Questions a pipeline generates for the human go to the human — enforce it
  mechanically (added 2026-07-29).** When an interview/spec pipeline produces
  questions for the user, relay them verbatim and wait; self-answering the
  "obvious" ones defeats the pipeline's purpose. If the soft rule alone keeps
  failing (ours failed twice in one night, and the transcripts showed the
  failures weren't tied to the suspected model — a gate defect, not a model
  quirk), promote the relay check to a fail-open hook instead of
  re-emphasizing the prose.

- **Before creating a personal-scope skill, check project scope for the same
  name.** Skill precedence is `personal > project` — the *opposite* of
  sub-agents — so a single personal skill silently disables a same-named
  project rule skill, with no warning or error. Checking costs one command
  (`bash scripts/scope-collision-check.sh <project-root>`);
  the failure mode is invisible. See the periodic-review rule for the standing
  check and for why nested collisions behave differently.

## 2. Design-before-implement (hard gate)
- "Let's build X" = present a design and get alignment **before** scaffolding
  or implementation. Exception: if the user explicitly said "proceed" under a
  standing autonomous instruction, design inline then implement (instruction
  priority — see autonomy.md §1).

## 3. Root-cause-before-fix (iron law)
- No fix before the root cause is found. Read errors, reproduce, check recent
  changes, gather evidence at component boundaries, trace data flow. Can't
  reproduce = gather more data, don't guess; never apply a phantom fix to a
  file that doesn't exist. 3+ failed fixes = question the architecture, stop
  and discuss.
- **Verify a "broken" premise before building a workaround**: before building a
  tool / daemon / workaround premised on an external tool being "broken," verify
  the premise itself — (a) measure it in *your actual version/config* (a reported
  bug may not affect your version), (b) read the *official docs* for a real
  control lever (issue trackers collect only failures and hide the working path),
  (c) don't trust a single source / tracker bias. Building a large artifact on an
  unverified premise is the costlier form of concluding absence from limited
  observation.

## 4. Delegation boundary
- Read-only sub-agents must not be trusted to have written (false-completion
  risk); independent worker processes may write. Verify a sub-agent's result
  before relying on it.

## 5. Diversity gate for automated loops
- Iterative LLM-driven mutation/optimization loops (self-improving search,
  evolve-style loops) drift toward an "attractor": repeated mutations revisit
  the same structural skeleton even as surface tokens change. Before a loop
  declares "converged/done," check skeleton-level diversity **once** — abstract
  recent accepted states to their skeleton (drop values/leaves, keep control
  structure) → hash → unique-ratio; a low ratio (only leaves swapped) = suspect
  attractor, not a true optimum. Inject diversity once (cross-model, a
  lateral/multi-persona pass, or diverse seeds), then re-judge.
- This is a **review gate** (inform-the-human, not auto-applied) and stays in the
  free read/draft zone — keep the commit/deploy boundary (autonomy.md §1).
- Verify the metric responds to the genome before trusting an optimization run:
  a coarse pass/fail metric can be insensitive (flat) and make every variant look
  equal; confirm sensitivity on extremes first, switch to a rank-aware metric if
  flat.

## 6. Case feedback → don't over-harden into universal rules
- When porting a case-specific correction (one piece of content, one screen, one
  incident) into a skill/rule file, do **not** promote it to a universal
  "never/always". Carry three markers: (a) an "in this case" qualifier preserving
  context, (b) explicit room for situational re-judgment, (c) the human's latest
  feedback always wins.
- This is the *write-to-file* counterpart of the assertion-lint (cross-checking
  "never/always/must" before committing to it): writing "never/forbidden/always"
  into a skill or rule is itself the self-check trigger.

▶ Fill in: where your case-vs-universal corrections get recorded.

▶ Fill in: which skill system you use + how to invoke it; your debugging
process doc; your sub-agent vs. worker delegation tools; your automated-loop
tool(s) and where the diversity check is recorded.

## 7. Solo work needs a written plan it keeps re-reading (2026-07-26)
- Meeting-based work has a shared ledger (context files, progress log) that keeps
  agents anchored; **solo work has no anchor unless you make one.** A plan that
  exists only as chat output evaporates, and mid-task purpose drift follows.
- For any non-trivial solo task: (a) generate the plan via your planning/prompt
  tooling, (b) **land it in a file** at a known spec location (never chat-only),
  (c) **re-read that file at every milestone or change of direction** — it plays
  the role the meeting progress log plays for group work, (d) patch the file in
  the same turn any scope change arrives (live-spec discipline).
- Whatever planning path produced it (interview pipeline or prompt generator),
  the landing contract is the same: known location + a deadline stamp + a stated
  done-condition. Small one-shot tasks are exempt — don't over-harden.

▶ Fill in: your spec directory for solo plans; your planning tool names.

## 8. Every rule needs a named owner and a place where it gets exercised (2026-08-08)

- When writing a new rule, fill three slots **inside the rule's own paragraph**:
  ①who acts ②when (which turn) ③where it lands. **A rule that can't fill them
  is incomplete — hold adoption** until it can.
- Why: a rule with no named actor gets done by nobody. And when no owner is
  named, the *default* wins — and defaults favor the common path, not the safe
  one. Observed across three independent agents in one audit: whether the agent
  *authored* the rule was not the variable; **having a designated place to step
  was**. This is rule design, not personal diligence.
- Optional check layer: a warning-only lint on rule-file edits that flags a new
  section with no owner slot. Keep it advisory — a blocking gate here slows
  rule-making more than it saves.
- Owner of this entry: the rule's author, in the rule's own paragraph (a
  separate registry table just creates a new empty slot).

## 9. Detection → prevention promotion review (three-strikes, 2026-08-08)

- Judgment sentence: **"if a detection process is attached and the incidence
  doesn't fall, the process makes metrics — not fewer defects."**
- Criterion: after detection exists, the **third recurrence of the same defect**
  makes that item a *candidate for review* for promotion to a prevention-layer
  fix (change the workflow so the defect can't be typed, rather than catching it
  after). **Review, not auto-promotion** — detection is the right layer for many
  items; "move everything to prevention" is over-hardening. The "3" threshold is
  a working floor (distinguishes from two coincidences), tune it to your data.
- Owner of the entry: **the agent who observes the third recurrence** writes one
  line in the shared progress log ("promotion candidate: <item>, 3rd time").
  The observer is the recorder — a separate tally-keeper slot just goes empty.
