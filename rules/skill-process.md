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
