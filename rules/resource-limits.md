# Rule: Disk & log resource limits (pre-flight + bounded sinks)

Trigger: about to start disk-heavy work (bulk generation, large clones/builds,
long agent/worker runs, media batches); configuring logging for a long-running
daemon; free-space or "no space left on device" (ENOSPC) signals appear;
session-start context looks abnormally large.

> Why: 2026-07-13 upstream incident — a data volume sat chronically ~99% full
> (an OS-update snapshot pinned ~85GB nobody was watching) while a worker's
> transient writes burned several GB/min; headroom hit 0 twice and every write
> on the machine failed, including the agents' own output. Same night, one
> daemon's default `debug`+`trace` tracing produced a single 32GB log file
> (~0.7GB/min). Neither had a pre-flight check nor a bounded sink; a >2GB
> single-file probe would have flagged the log ~30 min before the volume-level
> alarm.

## 1. Pre-flight headroom gate (before disk-heavy work)
- **Measure free space first** (`df -h <volume>`), not from memory or an old
  reading. Require headroom ≥ **max(15GB, 2× the expected transient peak)**;
  below that, do not start — clean up or escalate first.
- Long runs: **re-measure periodically** (every ~30–60 min or between
  batches). A passing pre-flight is a snapshot, not a lease.
- On any ENOSPC / <5GB signal: **full HOLD on all writers** (your own included)
  + alert the user. Do not "finish the current batch" on a full volume —
  partial writes corrupt state files.

## 2. Bounded log sinks (long-running daemons)
- Verbose tracing (`debug`/`trace`-level, per-span logging) stays **opt-in**,
  never the launcher default. Default to `warn`-level or the platform norm.
- Pipe daemon output through a **size-bounded rotating sink** (e.g. cap ×
  N generations) instead of an unbounded `> file`. Unbounded daemon logs are
  a disk incident on a timer.
- Watch for the early signal: any **single file >2GB** in temp/log/cache dirs
  is worth an alert with the filename — file-level probes fire well before
  volume-level percentage alarms.

## 3. Session-start context budget (agent harness)
- **Know your fresh-session baseline**: measure a new session's first-call
  token total (interactive: `/context`; headless: first `usage` entry in the
  session transcript). Startup context is pure overhead re-cached into every
  session and subagent — treat drift past your ceiling as an incident, not
  a curiosity.
- The usual silent inflator is **remote MCP tool schemas** — e.g. claude.ai
  account connectors synced into CLI sessions after an account (re)login.
  Adopting a multi-account proxy is a common trigger: in the upstream case it
  jumped session start from ~155k to ~400k tokens with zero local config
  change, on the same client version.
- **Levers (client-side)**: per-server blocklist (`deniedMcpServers` in user
  settings — does not touch the account's web connectors), account-connector
  kill-switch (`disableClaudeAiConnectors: true`), and on-demand tool-schema
  loading (env `ENABLE_TOOL_SEARCH=true` — a fresh session then reports
  `MCP tools … 0 tokens (loaded on-demand)`). Instruction-file diets help
  too, but measure first: tool schemas usually dominate.
- **Verify with the same instrument** before/after (upstream case:
  ~400k → ~140k), and add the metric to your periodic health packet with a
  threshold — the upstream climb ran 5 days unalerted because nothing watched
  this axis.

▶ Fill in: your volume(s) to watch, headroom floor if your workloads differ,
log cap/generations, session-start context ceiling (upstream default: 250k on
a 1M window), and where alerts should go (channel/user).
