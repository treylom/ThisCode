# Repo-Handoff Install Contract (ThisCode ⇄ ThisCodex — shared, normative)

Mirror of the canonical copy in `ThisCodex/docs/repo-handoff-install-contract.md`.
Bundled here under ThisCode's `contracts/` convention. Both repos' entry skills
(`skills/init/SKILL.md`, `skills/thiscodex/SKILL.md`) reference this. Keep in
lockstep with the canonical copy (drift-checked across the paired runtime).

1. **Default = interactive guided onboarding.** Whoever receives the repo —
   a human or an AI agent — the first/default install path is the guided one.
2. **Non-interactive only on explicit opt-out** (`--non-interactive`, `--yes`,
   `--answers`, or a documented CI/automation env). Never the default; never
   step 1 in entry docs/README.
3. **AI agents handed the repo MUST run the guided flow and relay each question
   to the user** (via their session/TUI), one at a time. They MUST NOT auto-run
   a non-interactive install, fabricate an answers file to skip questions, or
   report "copied = installed" / placement as completed onboarding.
4. **Missing required decision ⇒ safe-stop**: zero placeholder, zero
   half-install, print why + recovery. When input is possible, present in-place
   recovery (① continue interactively ② explicit non-interactive opt-out
   ③ abort); the non-interactive command appears only as the opt-out branch,
   never as the sole next step. When input is impossible (CI / non-TTY): clean
   stop + next command + non-zero, never hang, never self-answer.

Source design: `ThisCodex/docs/2026-05-18-repo-handoff-interactive-default-design.md`
