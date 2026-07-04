# Installing the fable verification hooks

These hooks are the mechanical half of `fable-work`: an evidence ledger that
records what actually ran, and a stop-gate that won't let a turn end
claiming "done" on a harness/code change it never verified. They are plain
Python scripts driven over stdin/stdout — no dependencies beyond Python 3.

This guide is for **Claude Code**. The same two scripts work in any harness
that can run a command on a post-tool event and on a turn-end event; only
the wiring syntax differs. If you're on **Codex**, prefer the upstream
plugin instead — see [`../codex/README.md`](../codex/README.md).

## The three files

| File | Role | Hook event |
|---|---|---|
| `fable_lib.py` | shared library (surface heuristic, ledger, gate logic, kill switch). The other two import it. | — |
| `verify-ledger.py` | records real verifications (test run / scan / cross-check) as ordered evidence. Records only, never blocks. Fail-open. | `PostToolUse` |
| `stop-verify-gate.py` | if the turn changed a code/harness surface with no verification recorded since, emits `{"decision":"block"}` to bounce the stop once. Capped, fail-open. | `Stop` |

## Install (Claude Code)

**1. Get the files onto your machine.**

```bash
git clone https://github.com/treylom/fable-work
```

(Or copy just the `hooks/` directory somewhere — if you do, adjust the
`fable-work/hooks/...` paths in the commands below to wherever you put it.)

Pick a stable absolute path for the three files — e.g. `~/.claude/fable-hooks/`:

```bash
mkdir -p ~/.claude/fable-hooks
cp fable-work/hooks/fable_lib.py fable-work/hooks/verify-ledger.py \
   fable-work/hooks/stop-verify-gate.py ~/.claude/fable-hooks/
```

**2. Wire them into `~/.claude/settings.json`.**

Add the two hooks to the `hooks` block (merge with anything already there —
don't overwrite existing hooks). Use the **absolute path** from step 1:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|Bash",
        "hooks": [
          { "type": "command", "command": "python3 $HOME/.claude/fable-hooks/verify-ledger.py" }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "python3 $HOME/.claude/fable-hooks/stop-verify-gate.py" }
        ]
      }
    ]
  }
}
```

`verify-ledger.py` goes on `PostToolUse` (matched to the tools that change
state — `Write|Edit|Bash`); `stop-verify-gate.py` goes on `Stop`, which
takes no matcher — it always fires on every turn-end. Both scripts find
`fable_lib.py` next to themselves, so keep the three together.

> **If you already have `PostToolUse` or `Stop` hooks**, don't paste this
> block over the existing key — that silently clobbers them. `PostToolUse`
> and `Stop` are *arrays* of matcher-groups, so **append a new object** into
> the array you already have. E.g. adding to an existing `PostToolUse`:
>
> ```json
> "PostToolUse": [
>   { "matcher": "...", "hooks": [ /* your existing hook */ ] },
>   { "matcher": "Write|Edit|Bash", "hooks": [
>       { "type": "command", "command": "python3 $HOME/.claude/fable-hooks/verify-ledger.py" } ] }
> ]
> ```

**3. Confirm it's actually wired (don't assume).**

```bash
python3 fable-work/hooks/tests/test_gate.py
```

This drives the hooks as real subprocesses and asserts the gate blocks when
it should and passes when it should. A green run is the runnable proof the
gate is live — which is the whole point (a rule you can't see fire isn't
enforcement).

## Turning it off / scoping it

Environment variables, read by `fable_lib.py`:

| Env var | Effect |
|---|---|
| `FABLE_GATE_OFF=1` | kill switch — disables the stop-gate entirely (the ledger still records; nothing blocks). |
| `FABLE_GATE_PILOT=<name>` + `FABLE_SESSION_NAME=<name>` | scope the gate to **one** named session, so you can pilot it on a single bot/agent before enabling it everywhere. With neither set, the gate is active for every session. |
| `FABLE_STATE_DIR=<dir>` | where the evidence ledger is written (default: outside the project tree, so verification bookkeeping never gets committed). |

The gate is deliberately narrow: it only fires on harness/code-surface
changes, never on plain notes/markdown, and it's capped at
`MAX_STOP_BLOCKS` bounces so it can't loop forever on genuinely-stuck work.
It fails open — any exception in the hook exits cleanly rather than wedging
your session.
