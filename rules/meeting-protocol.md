# Rule: meeting protocol · dispatch verification

Trigger: coordinating a multi-agent meeting, dispatching a bot, relying on a
bot's progress, or stopping while an active meeting is open.

## 1. SessionStart injection contract
- Inject only generic active-meeting state and the rules INDEX.
- Derive meeting paths from `MEETING_PROTOCOL_DIR`, `MEETING_ACTIVE_FILE`,
  `BOT_WD/meetings`, or `PWD/meetings`. Never hardcode a maintainer vault path
  or a Discord thread id in shipped files.
- Missing active meeting or rules INDEX = graceful no-op.

## 2. Dispatch verification
- "Dispatched" is not "working." Verify execution by at least one concrete
  signal: progress-file start row, process/tmux activity, test output, or a
  delivered channel progress message.
- If no execution signal appears within the meeting cadence, re-drive the
  teammate with executable input instead of waiting.

## 3. Progress file discipline
- Every meaningful start/done/blocked transition gets one append-only row in
  the meeting progress file.
- Use KST timestamps for human-facing rows unless a repository-specific
  protocol states otherwise.

## 4. Stop-hook reread
- A Stop hook may request continuation only when all are true: bot session,
  active meeting file exists, and no recursive Stop hook is active.
- All other cases allow stop (empty stdout + exit 0). When it does request
  continuation it must use the Stop block-with-reason primitive
  (`{"decision":"block","reason":<actionable text>}`) — the Stop event has no
  hookSpecificOutput variant — never a vague warning.

## 5. Meeting watchdog (optional, recommended)
- Every meeting **should** be paired with a watchdog daemon when bots
  coordinate over time. The orchestrator starts it on thread creation and
  pushes progress via `--beat`; an external launchd/cron ticker calls
  `--check` on a fixed cadence (default ~5 min; the maintainer's vault
  runs ~3 min for a tighter liveness signal — pick what fits your team).
- Use `scripts/meeting_watchdog.py` (bundled, stdlib-only). Lifecycle:
  `--start <thread_id> --goal <goal> --tasks-total <N>` →
  `--beat <thread_id> --tasks-done <K>` (orchestrator) →
  `--check` (external ticker) → `--stop <thread_id>` (auto on
  goal_met ∧ tasks_done, or manual).
- **fail-closed = keep-active**: corrupt or absent manifest never
  terminates a live meeting. Only the orchestrator can satisfy the
  termination condition because Claude Code `/goal` has no
  machine-readable state surface (the script documents this).
- Wire the launchd/cron ticker once per machine; the rule applies per
  meeting. Skipping the watchdog is allowed for solo / single-bot work
  but discouraged the moment ≥2 bots are dispatched (see §2 and
  `docs/05-meeting-thread-protocol.md` §2.3).

## 6. Active push pattern (watchdog bot, not passive timer)
- The watchdog (whether a dedicated bot or the orchestrator itself
  fulfilling that role) MUST, at each beat / check interval, **actively
  ping each active meeting participant** in the thread with an explicit
  `<@user_id>` mention plus a one-line liveness probe (e.g. "status?"
  or "one-line progress please"). Pure timer-based "still waiting"
  or "WAIT" messages are an **anti-pattern**: they regress the
  watchdog into passive monitoring and let silent participants stall
  the meeting unnoticed.
- A participant that does not respond within N consecutive beats
  (default N=2 — pick a sensible value for your cadence) is logged
  as idle in the progress file. The orchestrator then re-drives that
  participant with **executable input**, not another wait message
  (see §2 "dispatch verification" — `re-drive the teammate with
  executable input instead of waiting`).
- The watchdog needs the bot roster (`user_id` per participant) to
  address each one. Take it from the orchestrator's SessionStart
  context, from the meeting manifest's active-participants list, or
  from the operator-maintained roster — never invent IDs.
- **Why** (2026-05-21 operator regression): a sub-agent went silent
  after an "ack" while its actual work hung; the watchdog reported
  "still monitoring" each beat without ever pinging the silent bot.
  The meeting stayed open for ~15 min before the orchestrator
  noticed. Active push closes that loop.
- **Done-waiting carve-out** — not every silence is a stall. When a
  meeting (or a single participant) is legitimately *blocked on a gate*
  (a user decision, an upstream deliverable, a build), silence is
  `done-and-waiting`, not stuck, and pinging it is noise. Three knobs,
  all driven by the manifest so the automated ticker AND any manual
  active-push respect the same source of truth:
  - **meeting-level** `blocked_on: <gate>` — the whole meeting is gated:
    suppress active-push for all participants until the gate clears.
  - **per-bot** `done_participants: <bot1>,<bot2>` — a participant
    finished its track and is done-waiting while *others are still
    producing*. Setting meeting-level `blocked_on` here would wrongly
    silence the active producers, so suppress only the listed bots'
    per-bot probe. Orthogonal to `blocked_on`; it lifts liveness nags
    only (gate-release events still reach the bot). Absent field → no
    change (backward-compatible). Implemented in `meeting-liveness.py`
    (`done_participants`).
  - **hang vs done-waiting** — the carve-out assumes the gate worker is
    *progressing*. If its long turn hangs, the carve-out would hide the
    stall forever. So anchor the block with a start timestamp:
    `blocked_on: <gate> (since=<ISO|HH:MM>)`. The watchdog re-measures
    `now - since` each tick; past an upper bound (default 20 min, env
    `MEETING_WATCHDOG_BLOCKED_STALL_UPPER_SEC`) it breaks the
    progressing assumption and escalates as a hang. A hung turn cannot
    receive a Discord mention, so escalation is a **human** push (ntfy,
    env `MEETING_WATCHDOG_NTFY_TOPIC`), never a bot mention. No `since=`
    → hang undetectable → keep full suppress (backward-compatible).
    Implemented in `meeting_watchdog.py` (`_blocked_since_age`) and
    `meeting-stop-reread.sh` (blocked_on reread skip).

## 7. Meeting roster includes the watchdog/schedule agent
- When a team has a dedicated watchdog / schedule-domain agent (the one
  that runs the liveness ticker and owns cadence), include it in **every**
  meeting roster — both the meeting `00-context` roster and the watchdog
  `--participants` list. A meeting the watchdog agent is not a member of
  cannot get consistent liveness, termination, and schedule visibility.
- **One-off announcements / rule propagation do NOT open a meeting** — use
  the team channel. Reserve meetings for >=2-agent, >=30-min real work.
- **Create the room first (hard rule)**: a >=2-agent collaboration / discussion
  / analysis on one topic IS a meeting → create the dedicated room (thread +
  progress files) **before** speaking; do not run it in the main channel. The
  convening / chairing agent sets it up — don't defer ("someone will set it up
  later" → main-channel drift is exactly the violation this blocks).

▶ Fill in: your active-meeting filename, progress-file path convention, and
meeting cadence.
