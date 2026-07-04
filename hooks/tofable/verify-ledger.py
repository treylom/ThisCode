#!/usr/bin/env python3
"""PostToolUse(Write|Edit|Bash) — fable verification-evidence ledger recorder.

fail-open: any exception exits 0 with no output (never blocks the work).
This hook only records; the Stop hook (stop-verify-gate.py) does the judging.

Origin: fable-ish-codex hooks/post_tool_use.py, adapted for Claude Code hooks.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from fable_lib import (
        add_unique,
        changed_kinds,
        changed_paths,
        detect_failure,
        load_ledger,
        read_stdin_json,
        save_ledger,
        verification_record,
    )
except Exception:
    sys.exit(0)


def main() -> int:
    try:
        input_data = read_stdin_json()
        if not input_data:
            return 0
        kinds = changed_kinds(input_data)
        paths = changed_paths(input_data)
        verification = verification_record(input_data)
        failure = detect_failure(input_data)
        if not kinds and not verification and not failure:
            return 0  # nothing worth recording — ledger untouched

        ledger = load_ledger(input_data)
        ledger["event_seq"] = int(ledger.get("event_seq") or 0) + 1
        seq = ledger["event_seq"]
        if kinds:
            ledger["changed_files_seen"] = True
            add_unique(ledger, "changed_paths", [p.strip() for p in paths if p])
            add_unique(ledger, "change_kinds", kinds)
            if any(k in {"harness", "code", "config"} for k in kinds):
                ledger["last_gated_seq"] = seq  # gated change → prior verifications go stale
        if verification:
            verification["seq"] = seq
            ledger["verification_results"].append(verification)
            ledger["verification_commands"].append(verification["command"])
        if failure:
            ledger["failures"].append(failure)
        save_ledger(input_data, ledger)
        return 0
    except Exception:
        return 0  # fail-open


if __name__ == "__main__":
    raise SystemExit(main())
