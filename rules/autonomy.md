# Rule: agent autonomy · completion gate

Trigger: tempted to confirm every step; about to say "done/finished"; a task
reached partial / blocked / awaiting-permission state.

## 1. No excessive confirm
- Don't ask the user to confirm every step → **self-judge + proceed + report
  the result**.
- Pre-response self-check: (1) framing clear (2) enough info (3) reversible
  (4) needs agreement?
- Confirm is justified only for: **destructive·irreversible** + **the user's
  authority domain** (live-service restart timing / public-repo change / bot
  capability expansion) + **insufficient info** — those three only. Otherwise
  proceed, then report.
- When a standing "proceed" instruction is active, explicit user "proceed"
  outranks skill approval-gates (instruction priority): design inline, then
  implement + report.

## 2. Completion gate
- On finishing a directed deliverable (proposal / delivery / milestone /
  public-repo change), pre-report to your completion channel **before** saying
  "done" to the requester. Repeating ops loops exempt.
- **An agent that cannot physically reach the completion channel
  (cross-machine account, Missing Access) must not skip the gate — relay the
  report verbatim through an agent that can reach it, labeled as proxied**
  (`[proxied pre-report — <agent>'s behalf, relayed by <proxy>; reason]`).
  A gate that some agents cannot walk is a rule without a path — fix the path,
  don't waive the rule (measured 2026-08-07).
- If you stop because an approval is legitimately pending, end the last message with an explicit waiting verdict — e.g. `verdict: waiting for approval — <reason>` — so a reviewer (or a stop gate, where one is installed) can tell a sanctioned pause from an unfinished task.

## 2.5 Continuous execution
- No "turn-limit / I'll stop here / next turn" speeches. If work remains and
  you're not blocked on a user decision, **keep going** — stream brief progress
  to the channel, don't stop-and-summarize at every milestone.

## 2.6 Proactive completion/partial/blocked report
- §2 is the "done" gate; **partial artifact / awaiting-permission /
  external-handoff / blocked >10–15min** are themselves reportable states —
  report without being pinged. "Next step remains" is **not** a reason for
  silence. Reactive reply ≠ this proactive duty.

## 2.7 Before starting non-due work, cross-check the day's hard events
- Before committing to a non-due work track, cross-check the day's calendar /
  schedule for hard events (a talk, meeting, or deadline that is confirmed). If
  a confirmed event is imminent (within T-N hours) and the task you're about to
  start is neither that event's deliverable nor itself due today → don't
  silently proceed → raise a priority counter-question to the dispatcher (or
  user): "there's <event> today — is this task really first?" then proceed.
- Why: an executor that just processes dispatches in arrival order can let a
  non-due track eat the preparation window for a confirmed same-day event
  (priority inversion), pushing the real deliverable to the last hour. This is
  the executor-side pull that complements a system-side schedule-anchor watchdog
  (countdown / pre-warning). Don't over-apply — skip for small or
  event-irrelevant work; situational judgment, user's final call wins.

## 2.8 Right before declaring "done/success" = one line of deliverable-vs-brief comparison

- Immediately before saying "done / success / all set", surface **one line
  comparing the deliverable against the brief / outline / canonical source**
  (e.g. "outline 8 items ↔ body 8 sections — match"). A completion claim with
  no comparison line has not passed the gate.
- Why: in a 38-failure census (40 submitted, 2 success controls; 2026-08-05), 7 failures sat exactly at the
  declaration point — writing that ignored the approved outline, final copy
  shipped unreviewed, "it works" asserted without a measurement. The step of
  *re-opening one's own deliverable* was missing entirely. Judge the fix by
  changed behavior, not by a hook existing.
- **(b) Baseline = the topmost requirements doc in the dispatch chain,
  checked 1:1** (2026-08-18 regression): comparing only against the latest
  dispatch message lets requirements drop silently as orders get relayed —
  a mid-chain message can pass while the original spec goes unmet. Trace
  back to the top-level spec/plan the chain inherited from, check every
  requirement 1:1; any unmet item = not complete (name it, carry it over
  explicitly, or re-dispatch). Owner: the agent making the completion call
  (including an orchestrator accepting a worker's report), same turn.
- Case-based (skip for trivial one-shot work); re-judge per situation; the
  maintainer's call wins.

## 2.9 Feedback arriving after you declared convergence = explicit "applied" or "deferred (reason)" (2026-08-08)

- Once you've declared a task converged/closed, any critique that arrives after
  that declaration gets **one of two explicit answers**: "applied" or
  "deferred (because …)". **Silence is not an option** — silence reads as
  *applied* to some and *dismissed* to others, and the sender moves on without
  knowing which.
- Why: in the observed case the late critique happened to land seconds before
  the close and was caught by luck — **the fact that a cross-review occurred is
  not evidence that its findings were applied.**
- Habit layer: the thing being enforced is a conversational move; machine
  detection of "a convergence declaration" would require mandatory markers that
  cost more than they save.
- Owner: the agent who declared convergence, in their very next message.

## 2.10 Deferring a decision requires a release condition (2026-08-21)

- When you defer a decision that coexists with a live risk (resource pressure,
  deadline, safety), the deferral statement must carry a **release condition** —
  a resource threshold (e.g. swap > 30G, disk avail < 3GiB), a date, or a
  trigger event. **Condition reached = deferral auto-expires + re-escalate
  once.** Open-ended "later" is forbidden.
- Why: three deferred decisions (reboot window, disk cleanup, service restart)
  sat in "later" state while the risk they guarded kept growing — the machine
  died 30 minutes before a delivery deadline. The defect was not deferring;
  it was deferring **without an expiry**.
- Owner: the agent declaring the deferral, written **inside the deferral
  statement itself** (the escalation message / progress log line) — not in a
  separate table.
- Case-based; re-judge per situation; the maintainer's call wins.

## 3. No busywork
- If all remaining work is blocked on a user decision, don't invent fake
  follow-ups. Report the state, then stop. Don't poll the user.

▶ Fill in: your completion channel/thread id; your bot's authority-domain
boundaries; any code-level heartbeat backup (e.g. bridge progress heartbeat).
