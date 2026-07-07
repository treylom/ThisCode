#!/usr/bin/env python3
"""PreToolUse (Bash) — blind-retry gate (ledger v4, mined behavior C3).

When the immediately preceding Bash command FAILED and the incoming call is
the byte-identical command, bounce it ONCE: diagnose before retrying. The
mined fable behavior at error sites is never "run it again" — it is "change
the conditions": a blocked file: protocol became a local http server, a
missing table became a schema introspection, a timeout became a state probe
(capture-pane/pgrep). The incident corpus shows the inverse habit at its
worst: one bug was re-attacked 15 times with untested guesses.

Contract mirrors surfacing-gate: deny once per command hash, the identical
re-run passes after the bounce (an intentional retry after a transient flake
costs exactly one bounce), any DIFFERENT command resets the chain, session-
wide cap bounds worst-case friction, fail-open on any exception, same kill
switch (FABLE_GATE_OFF / FABLE_GATE_PILOT).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from fable_lib import MAX_RETRY_BLOCKS, gate_enabled, load_ledger, read_stdin_json, save_ledger
except Exception:
    sys.exit(0)

REASON = (
    "blind-retry-gate: this exact command just failed, and this call would "
    "re-run it unchanged. An error is data — read it before spending another "
    "attempt: (1) name the failure cause from the error output, (2) run one "
    "probe that tests that cause (stat the path, introspect the schema, "
    "check the process/port), or (3) change the command to route around it. "
    "If you have genuine reason to believe the failure was transient, re-run "
    "the identical command now — it passes after this bounce."
)


def command_of(input_data: dict[str, Any]) -> str:
    tool_input = input_data.get("tool_input")
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or "")
    return ""


def cmd_hash(command: str) -> str:
    return hashlib.sha256(command.strip().encode("utf-8", "replace")).hexdigest()[:16]


def main() -> int:
    try:
        input_data: dict[str, Any] = read_stdin_json()
        if not input_data:
            return 0
        if str(input_data.get("tool_name") or "") != "Bash":
            return 0
        if not gate_enabled():
            return 0
        command = command_of(input_data)
        if not command:
            return 0
        ledger = load_ledger(input_data)
        if not ledger.get("last_bash_failed"):
            return 0
        digest = cmd_hash(command)
        if digest != str(ledger.get("last_bash_cmd_hash") or ""):
            return 0  # different command — the chain is already broken
        bounced = ledger.get("retry_bounced")
        if not isinstance(bounced, list):
            bounced = []
        if digest in bounced:
            return 0  # identical re-run after the bounce — intentional retry
        if int(ledger.get("retry_blocks") or 0) >= MAX_RETRY_BLOCKS:
            return 0  # session cap reached — stop adding friction
        bounced.append(digest)
        ledger["retry_bounced"] = bounced[-40:]
        ledger["retry_blocks"] = int(ledger.get("retry_blocks") or 0) + 1
        save_ledger(input_data, ledger)
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": REASON,
                    }
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception:
        return 0  # fail-open


if __name__ == "__main__":
    raise SystemExit(main())
