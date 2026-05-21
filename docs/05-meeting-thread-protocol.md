# Meeting Thread & Channel Governance Protocol

> **Policy SoT**: vault `.claude/rules/channel-governance.md`  
> **Domain**: Dr. Strange (schedule / channel governance)  
> **Status**: Active — 2026-05-16

---

## 1. Conversation Log Archiving

Archive **final deliverables only** — never raw chat logs.

| Preserve | Discard |
|---|---|
| Proposals, deliverables, docs, code outputs | Raw Discord message history |
| Meeting outcomes (4-file template) | In-progress iteration logs |
| Repo commits | Intermediate conversation threads |

Store each output where it belongs:
- **Meeting** → `meetings/<date>-<topic>/` (4-file template)
- **Code** → repo commit
- **Document** → vault folder

Only archive outputs that have passed the completion gate. Process logs are ephemeral by design.

---

## 2. New Work Topic = New Thread

Open a **new thread** in your main team channel for every new work topic.

```
Main channel body  →  redirect notice only
Thread             →  all discussion, decisions, outputs
```

This applies to: meetings, task reviews, design sessions — any bounded unit of work. Keeping topics in threads preserves searchability and prevents channel noise.

### 2.1 Autonomous cycles count as meetings

If an orchestrator bot dispatches work to two or more bots — even informally, even from an autonomous `/goal` session, an overnight cycle, or a direct ping — that is a meeting trigger. The thread + meeting-folder requirement applies. "Informal" is not an exemption: when audience bots reply, they default to the main channel or the completion-report thread unless told otherwise, which cascades into channel-governance violations.

Self-check before dispatching to any teammate bot:

> Will this involve ≥2 bots, or take ≥30 minutes? If yes, open the thread first.

### 2.2 Dispatch messages must name the thread id

When you dispatch work to another bot, include the thread id explicitly in the message body:

> "Continue this work inside thread `<thread_id>`. Use the completion-report thread only for the final completion gate."

Without an explicit thread id, the receiving bot falls back to its default reply target (usually the main channel body or the completion thread), and the work surfaces in the wrong place. The orchestrator owns this — it cannot be retrofitted from the audience side.

### 2.3 Invite a meeting watchdog bot (optional, recommended)

Every meeting **should** include one extra agent acting as a watchdog — a daemon that monitors progress, detects silence/idle/incompletion, and surfaces drift back to the orchestrator. The maintainer's vault runs Dr. Strange on a ~3 min cadence; the bundled default is ~5 min (`scripts/meeting_watchdog.py`). Either works — pick what fits your team's signal-to-noise.

Two pieces:

1. **In-session orchestrator** pushes state via `--start` (thread creation) → `--beat` (each progress transition) → terminates on `goal_met ∧ tasks_done`.
2. **External ticker** (launchd / cron) calls `--check` on a fixed cadence; fail-closed = a corrupt or absent manifest keeps the meeting active (never false-terminates).

Why an explicit bot, not just a script: the watchdog is the only party that surfaces "this meeting has gone silent for N intervals" without the orchestrator self-grading. Skipping it is allowed for solo / single-bot work but is the first thing to wire up the moment ≥2 bots are dispatched.

| Component | Owner | Cadence |
|---|---|---|
| `--start` / `--beat` / `--stop` | Orchestrator (in-session) | Per progress event |
| `--check` (ticker) | launchd / cron | ~3–5 min (pick once per machine) |
| Liveness escalation | Watchdog bot or orchestrator | When `--check` flags stale beat |

See `rules/meeting-protocol.md` §5 for the lifecycle contract.

---

## 3. Cross-Machine Coordination = Dedicated Channel

Use a **separate cross-machine channel** when work crosses device or environment boundaries (e.g., Mac ↔ WSL ↔ external machine).

| Scope | Channel |
|---|---|
| Internal (same team, same environment) | Main team channel + threads |
| Cross-machine (different devices/envs) | Cross-machine coordination channel |

---

## Quick Reference

| Question | Answer |
|---|---|
| Save this chat log? | No — save the final output, not the conversation |
| Starting a new task or meeting? | Open a new thread in the main channel |
| Coordinating across machines? | Use the cross-machine channel |
| Where does the output go? | Follows output type (meeting/code/doc rules above) |

---

## Relationship to Other Docs

- `04-meeting-framework.md` — meeting structure (4-file template, agenda format)
- `skills/meetings/SKILL.md` — `/open-meeting` skill usage
- vault `.claude/rules/channel-governance.md` — policy SoT (authoritative)

---

*Maintained by: Dr. Strange · Last updated: 2026-05-16*
