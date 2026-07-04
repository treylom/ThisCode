#!/usr/bin/env python3
"""Stop — fable verification gate.

Behavior: if this session recorded a harness/code-surface change with no
successful verification evidence **after** that change, print a stdout JSON
{"decision":"block","reason":...} to bounce the Stop once (hookkit
hk_block_stop convention). Capped at MAX_STOP_BLOCKS, passes through when
stop_hook_active is set (loop guard), fail-open on any exception.

Pilot gate: active by default for every session. Disable entirely with
FABLE_GATE_OFF=1, or scope activation to one named session with
FABLE_GATE_PILOT=<name> (see fable_lib.gate_enabled docstring). This keeps
the gate off the free-exploration/drafting phase of a workflow and only
applies to harness/code surface changes — never plain notes/docs.

Origin: fable-ish-codex hooks/stop_gate.py, adapted for Claude Code hooks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from fable_lib import (
        gate_enabled,
        load_ledger,
        read_stdin_json,
        save_ledger,
        should_block_stop,
    )
except Exception:
    sys.exit(0)


def main() -> int:
    try:
        input_data = read_stdin_json()
        if not input_data:
            return 0
        if input_data.get("stop_hook_active") is True:
            return 0  # already inside a Stop-hook chain — don't re-block (loop guard)
        if not gate_enabled():
            return 0
        ledger = load_ledger(input_data)
        block, reason = should_block_stop(ledger)
        if not block:
            return 0
        ledger["stop_blocks"] = int(ledger.get("stop_blocks") or 0) + 1
        save_ledger(input_data, ledger)
        # hookkit hk_block_stop convention: stdout JSON + exit 0
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
        return 0
    except Exception:
        return 0  # fail-open


if __name__ == "__main__":
    raise SystemExit(main())
