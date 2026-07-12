# Rule: multi-agent orchestration

Trigger: delegating to / waiting on another bot, convening a meeting,
asserting another bot's identity or health, or coordinating multiple agents.

## 1. Bot identity = verify, never assume
- A bot's identity SoT is the persona injected at session start for **its own**
  `<bot>` (derived from its state dir / `~/.../discord-<bot>`), plus its own
  working-directory context file.
- **Chain-load guard**: agent runtimes load every context file from cwd up to
  the repo root. If a shared/root context file (`CLAUDE.md` / `AGENTS.md` /
  `GEMINI.md`) also doubles as one specific bot's WD meta ("I am X"), every
  other bot whose WD sits under that root chain-loads it and can absorb that
  identity. Put an **identity guard at the very top** of any such file: "this
  identity block applies only when `<bot>` == X; otherwise ignore it — your
  identity is your own injected persona + your own WD context." A bot speaking
  in another bot's voice / self-referring as another bot = this guard missing.
- The orchestrator **verifies** a teammate's session/identity/health (live
  check, source-fact) before delegating or waiting. "It's probably working" by
  assumption, then waiting, is dereliction.

## 2. Drive, don't idle (collaboration-boundary distinction)
- Teammate is the gate but idle/blocked → orchestrator actively re-engages
  **via the channel**: re-send the request (mention/reply), and run non-gating
  tracks in parallel (e.g. collect the *data* yourself so the teammate's
  judgement step is unblocked).
  - ⚠️ **Never inject input into a peer bot's `tmux` session.** "Drive" does
    **not** mean typing into another bot's input buffer — that strips
    provenance = internal prompt injection. tmux is read-only; signal via the
    channel. Channel re-send still silent = bridge problem (no workaround) →
    escalate. See discord-comms §5. (A human operator's session-meta send —
    `/compact`·`/clear` — is the normal exception, discord-comms §5 R5.)
- Distinguish: **blocked on a user decision** → summarize, report, stop (no
  polling). **Teammate idle / oversight** → not a stop; drive and verify. Do
  not conflate the two into passive waiting.

## 3. Meeting facilitation (no solo lock)
- Convener does not force its own frame; adopt each bot's domain prep frame as
  that domain's SoT, register frames separately, keep your draft as one input.
- Lock only after: gate teammate's output → meeting consensus → independent
  review → second-track review → maintainer sign-off. No single step skipped.

▶ Fill in: how `<bot>` is derived in your setup; your identity-guard location;
your independent-review + second-track reviewers; your maintainer sign-off path.

## 4. Debugging = co-engage a second, independent reviewer (no solo closure)

- When a **non-trivial bug** surfaces (reproduction, root-cause hunting, or
  fix verification is at stake), the discovering bot does not close it alone.
  Bring in an independent engineering peer (a different bot/engine — e.g. a
  Codex-side reviewer if the finder runs on Claude) in one of three shapes:
  ① independent reproduction/diagnosis on a different hypothesis axis
  ② cross-review of the proposed fix ③ parallel repair on an isolated
  branch/worktree. State the shape explicitly in the dispatch (HOW-complete).
- Mind machine boundaries: a peer on another machine joins local-only repro
  work as the diagnosis/review axis; if the repo is on a shared remote, it can
  reproduce directly.
- **Trivial escape hatch**: typos and 1-hop self-evident fixes may go solo —
  but leave a one-line judgment note in the progress log / commit.
- Rationale: a single-viewpoint debug leaves sibling bugs and detection gaps
  behind; an independent second viewpoint is the cheapest cross-check.

▶ Fill in: which peer bot/engine serves as your debugging co-reviewer; where
its dispatch channel lives; your progress-log path for the judgment note.

## 4.5 Security domain = dedicated security lineage first (NEW work only)

- **New security work** (integrity / tamper-resistance, sealing, adversarial
  audits (incl. attack reproduction) — from planning through verification) goes to
  your designated security-verifier lineage (an engine/bot independent of the
  implementer), not to the implementing bot itself.
- Non-security work (experiment bodies, feature verification, data recording)
  stays with its current owners.
- **Assignment default, not a retroactive purge**: a direction like "security
  goes to X" sets the default for NEW assignments. Healthy in-flight tracks
  keep their current owner — forced mid-flight transfers churn a working
  pipeline. If retroactive re-assignment seems warranted, confirm with the
  maintainer in one line first. (Learned from two same-day over-application
  regressions: a scope directive ballooned into "halt everyone", then into
  "transfer healthy in-flight work".)
- The orchestrator does not re-derive security verdicts (no hash
  re-derivation / probe re-runs) — it accepts the security reviewer's verdict
  and coordinates flow. Non-security gates keep their existing owners.

▶ Fill in: your security-verifier lineage (bot/engine); grandfathered
in-flight tracks; your maintainer-confirmation channel.
