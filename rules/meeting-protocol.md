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
- **Spill rule**: when the progress file exceeds ~100 rows, move detail
  blocks (long analyses, logs, tables) into a numbered doc (`NN-*.md`)
  and leave one row: `[KST] <bot> | spill | →NN-doc`. The progress file
  keeps only decisions, pointers, and gate states — test: "does reading
  the progress file alone give the flow?" (guards against spilling so
  much that the source of truth scatters).
- **Cross-check mandate (no single-bot assignment)**: never hand a meeting
  agenda item to one bot end-to-end. Every substantial output gets ≥2 reviewers
  from *other* domains who actually read it and must surface concrete defects,
  gaps, or counter-evidence (agreement summaries don't count); disputed points
  converge in a discussion round, and unresolved ones escalate to the human
  owner. Large meetings may split into sub-threads per agenda group while
  keeping one canonical progress file.
- **Append integrity**: never append to a progress/SoT file via shell `echo` —
  escape interpretation can inject literal control bytes (a single NUL byte can
  make the whole file invisible to grep-class search). Use `printf '%s\n'`,
  `print -r --`, or a python append. **The command is only half of it — the
  quoting matters too.** `printf` and `print -r` still perform command
  substitution on backticks and `$` inside *double* quotes, so what lands in the
  file is that command's output, not the text you wrote. Do not rely on stderr
  or exit status to catch this: if the backticked text happens to be a valid
  command, stderr is empty, exit is 0, and a plausible-looking value lands in
  the file; if it is not a valid command, exit is *still* 0, and in a simple
  command the error escapes `2>` entirely because expansion runs before the
  redirection is installed (wrapping the append in `{ …; } 2>file` or a subshell
  does capture it, but only when the substitution was an invalid command). The
  NUL / UTF-8 checks below pass in every one of these cases. So: **put such
  content in single quotes or a quoted heredoc (`<<'EOF'`), and verify by
  confirming that one or two distinctive anchor tokens from your text actually
  survived in the file** — that anchor check is the only detector covering both
  halves, and "the file looks fine" is not evidence. A wrapper that captures
  stderr would catch only the invalid-command half — it does not replace the
  anchor check. **Separately — for the `echo` failure above —** check once after
  appending for NUL /
  invalid UTF-8 — but not with `grep -c $'\x00'` (most shells cannot pass NUL
  in argv; the empty pattern then matches every line, returning a line count
  regardless of content). Use
  `python3 -c "import sys;print(open(sys.argv[1],'rb').read().count(bytes([0])))" <file>`
  or `tr -dc '\000' < <file> | wc -c`. When introducing or distributing any
  check command, ship it with a positive control (seed the defect once and
  confirm the check catches it). When reporting a live file's state, include
  hash + mtime + observed-at together, and name the comparison hash when
  claiming before/after.
- **Same-account dual-instance owner declaration**: if the same bot account can
  run as two instances (e.g. terminal + channel), declare the owner on the first
  progress-file row (`owner=<which> <bot>`); a non-owner instance must not write,
  dispatch, or fire the completion gate for that meeting. Coordinate between
  same-account instances **through the progress file only** — a channel mention
  does not reach your own account's other instance. An unfamiliar row under your
  own bot name = dual-instance signal → verify (mtime/tmux/fetch) before acting.
- **Idle judged on 3 axes + append-race row-survival check**: don't conclude "idle" from
  a silent progress file + idle terminal alone → also weigh the token/context
  gauge (rising = working) and the thread's fetched messages. Concurrent appends
  can lose a row (read-modify-write race), so after appending, confirm once that
  your row survived; re-append if lost (race ≠ idle). **Do not run that check
  with `tail`.** A live progress file keeps being written after your own write —
  if another participant appends in the seconds between your write and your
  check, `tail` hands you *their* row, and reading it as yours produces a false
  "my row was lost" (and then a duplicate re-append, or worse, a "recovery" that
  edits the wrong row). Locate your row by its timestamp or a distinctive anchor
  string instead of by position. **If a recovery step deletes or rewrites rows,
  guard it with an assertion that the target row is the one you think it is** —
  when a filter built from assumptions meets a file that has moved on, that
  assertion is the only thing standing between you and deleting someone else's
  record.

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
  - **`since=` is for worker-hang gates ONLY**: it encodes a *progressing
    assumption* (a bot/CLI turn that should finish). If the gate is an
    indefinite **human decision wait** (`awaiting_<user>_directive`-style),
    there is no progressing assumption — adding `since=` there just
    manufactures false hang escalations every upper-bound interval (ntfy
    spam). Deliberately omitting `since=` on human-wait gates is the
    correct form, not an omission.
  - **Refresh the `since=` anchor on worker activity**: if the gate stays
    up but the worker visibly produced something (output, pivot), move
    `since=` to that latest activity timestamp — a stale anchor turns
    legitimate long gates into false hangs. Timestamps in `since=` are
    UTC `Z` form (a naive local time is misread by the watchdog).

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
- **Bridge-based teammates → prefer a monitored room**: when dispatching long
  or multi-step work to an agent that lives behind a bridge / different harness
  (e.g. a Codex CLI bot relayed through a channel bridge), prefer opening a
  meeting room (thread + progress files + watchdog) over reusing an ad-hoc
  thread — the liveness ticker attaches automatically, so bridge lag and silent
  no-pickup get caught early instead of after hours. Small one-shot asks may
  still go direct (judgment call; operator preference wins).

▶ Fill in: your active-meeting filename, progress-file path convention, and
meeting cadence.

## 8. LATEST.md pointer (long meetings)

- For meetings with 3+ milestones or a long progress log (30+ rows), keep **one `LATEST.md`** in the meeting folder so a newly joining (or post-compaction) agent can sync without rereading the whole log. ≤10 lines: current phase / blocked_on / per-agent one-liner / next gate / `evidence: progress row [HH:MM]` / last-updated timestamp.
- The dated progress log remains the append-only source of truth; LATEST.md is a *pointer/summary* — on conflict the log wins.
- **Atomic update + no-op duty**: write temp file → `mv` swap (never expose partial writes). If content is unchanged, do **not** rewrite (mtime noise reads as a false "something changed" signal). Real file only — no symlink (breaks across machines/sync).
- Owner = the chairing agent, updated at milestones (lock/dispatch/gate-passed/hold-resume). Short one-shot meetings may skip it.

## 9. Cross-check & debate — no single-owner agendas (operator hard rule)

- **Never run a multi-agent meeting as a pile of solo assignments** (each agent
  writes its own doc and the meeting output is just their concatenation). Every
  substantive prep/output doc gets **≥2 reviewers from *other* domains** who
  actually read it and post defects / additions / counter-evidence through
  their own lens — a bare "agree" summary does not count as a review (aim for
  ≥2 concrete items per lens; support quantitative claims with at least one
  actual measurement — the fold-back and measurement clauses are derived
  team practice, not the operator's literal words; the hard rule itself is the
  ≥2 cross-domain reviewers + debate + escalation + sub-room split).
- Corrections are folded back by the **original author** (annotated, not
  silently rewritten); diverging points get a debate round in the meeting
  thread; divergence that remains after debate escalates to the operator —
  never resolved by silent majority or the chair's solo call.
- Large meetings may split into sub-rooms (per agenda-group sub-threads +
  numbered doc anchors), but keep **one** canonical 4-file record.
- Why (operator hard rule, 2026-08-01): round one ran as single-owner
  distribution, so defects sat unchallenged inside finished docs; the moment
  mandatory cross-review was inserted mid-meeting, it caught stale cited values
  and self-contradictions the authors had missed. Format precedent = a reviewer
  matrix in the meeting spec (doc × 2 reviewers × lens). Case-based
  (2026-08-01); re-judge per situation; the operator's explicit instruction
  always wins.

▶ Fill in: where your reviewer matrix lives (meeting spec section), who the
escalation counterpart is, and when sub-rooms are worth opening.

## Liveness 4th axis — outage vs idle

Even when all idle signals agree (no ledger append + idle terminal + silent thread), check one more axis: **are other bots / other paths silent at the same moment?** If yes, it is an *outage*, not idle — wake-pings and re-dispatches are no-ops there. Applies to automated daemons and manual probes alike. See the upstream-outage rung in discord-comms. Case-based (2026-07-25); re-judge per situation; the maintainer's call wins.


## 10. Live meeting canvas (channel shared surface)

When the meeting channel offers a shared document surface (e.g. a Slack channel
canvas), treat it as the meeting's **live shared board**, not a post-hoc
archive (operator rule, 2026-08-07 — measured in the first live bot-to-bot
Slack meetings):

- **Open first**: the canvas-capable bot opens/initializes the meeting canvas
  **with its first utterance** (agenda / roster / discussion-log / decisions
  skeleton) and posts the **canvas link** into the meeting thread — an
  "the canvas is open" announcement without the link leaves humans unable to
  find it (canvases created via API surface no channel message at all). A bot
  without canvas write access must **request** the canvas opening in its own
  first utterance instead of silently proceeding to the agenda.
- **Update during the meeting**: the scribe (canvas-capable) bot re-pushes the
  board whenever a substantive point or agreement lands. A single end-of-meeting
  dump is a partial failure of this rule. Contributions from bots without write
  access are folded in by the scribe — their thread messages are the
  contribution medium.
- **Close**: on conclusion, push the final decisions/follow-ups to the canvas,
  then post the minutes summary (`[회의록]`-style, agenda/roster/decisions/
  follow-ups) to the thread with the minutes file path.
- **Final archive = each participant's own knowledge base**: the canvas is the
  shared working surface; each bot mirrors the final minutes to its **own
  machine's** vault/KB — the authoring bot from its file, the others from the
  thread-posted minutes (absent canvas-read tooling, the thread post is the
  transfer medium). This is how cross-machine bots share one meeting record
  without sharing a filesystem. **Archive filenames must carry the writing
  bot's identifier** (`YYYY-MM-DD-<topic>--<bot>.md`): each participant
  archives its *own rendition* of the same meeting, so identical filenames
  mean any cross-machine vault sync lets one rendition silently overwrite the
  other (measured 2026-08-07: a sync replaced one bot's 5439-byte minutes with
  the other bot's 3599-byte transcription under the same name; the original
  survived in the repo copy — zero loss by luck, not by design).
- **Roster reality**: the minutes list only accounts that actually spoke or
  were tagged **in this thread** — never a name recalled from an earlier
  session (measured regression: a bot addressed an absent participant
  remembered from a prior test, self-corrected only after a human pointed it
  out).
- **"During the meeting" is a timing verdict — overlay two rulers**: the
  thread's message timestamps (complete, untruncated) and the canvas push
  log's timestamps. First push minus first utterance ≈ opened at start;
  pushes interleaved with message timestamps = live updates; pushes clustered
  after the last utterance = end-dump (partial failure). Neither ruler alone
  can make the call.

▶ Fill in: your canvas tooling (push command + push-log path) and each bot's
final-archive path.

## 11. Restarting an agent while a meeting may be live

Rule-file swaps and harness changes tempt an immediate restart — but a restart
kills the session's in-flight turn and its meeting memory. Two measured
incidents on 2026-08-07: one restart cut an unprocessed inbound mid-meeting;
one operator nearly killed a session that a wrong ruler reported as "296s
idle" while the meeting was active in thread replies.

- **Before restarting a resident agent session, check for an active meeting
  with a ruler that can actually see it**: a channel-history call that returns
  only top-level messages is blind to thread replies — use a thread-reply-aware
  read (`conversations.replies`-class) or look at the live session surface
  (tmux pane / gauge movement). "No new top-level messages" is not "idle."
- If a meeting is (or may be) live: defer the restart — a one-line rule delta
  can ride the next natural restart. Restart mid-meeting only for a defect
  that is itself breaking the meeting.
- The failure shape is the same early-stop family as detector truncation: the
  tool reports "nothing" about a region it cannot see, and the operator reads
  that as "nothing is happening."

## Liveness: two rulers, two questions

The ledger's (02-progress) **mtime answers "is this meeting alive"**
(file-level — cheap and sufficient for that question). **"Has this bot acted"
(bot-level) = the timestamp of that bot's own last row**
(`grep "] <bot> |" <ledger> | tail -1`). Using shared-file mtime for
bot-level liveness produces false positives — any other bot's append
refreshes it (live incident: two idle bots judged "just active"). Print "the
question this check answers" next to the check (see source-fact checker
discipline): the ruler was not wrong, it stood in the wrong spot with no
question attached. Case-based (2026-08-05); re-judge per situation; the
maintainer's call wins.
