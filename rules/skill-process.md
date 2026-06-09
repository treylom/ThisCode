# Rule: skill · process discipline

Trigger: starting a build/design ("let's build X") · debug · verify task;
an automated experiment loop; delegating to a sub-agent.

## 1. Skill-invoke gate
- creative / debugging / verification / build task = invoke the relevant skill
  **before** any response or action. If there's even a 1% chance a skill
  applies, invoke it.
- Priority: process skill (brainstorming · debugging) first → implementation
  skill. Conflict: **explicit user instruction > skill > default**.

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

▶ Fill in: which skill system you use + how to invoke it; your debugging
process doc; your sub-agent vs. worker delegation tools.
