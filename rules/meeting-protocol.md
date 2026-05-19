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
- All other cases allow stop. The hook must emit actionable context, not block
  with a vague warning.

▶ Fill in: your active-meeting filename, progress-file path convention, and
meeting cadence.
