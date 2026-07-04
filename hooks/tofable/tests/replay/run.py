#!/usr/bin/env python3
"""Replay corpus — re-play archived violation scenarios against the live gate.

Each fixture in fixtures/ is a violation that the gate is supposed to block:
a sequence of ledger events (changes / shell commands) followed by a Stop.
This runner replays every fixture through the real hooks (subprocess, same
contract as tests/test_gate.py) and reports the block rate.

Exit codes:
  0  — block rate 100% AND corpus size >= CORPUS_FLOOR
  2  — any fixture NOT blocked (a past violation would now slip through),
       or corpus shrank below CORPUS_FLOOR (deleting fixtures to fake 100%
       is itself a gamed metric — the floor makes that loud).

Operating rule: when a real violation slips through the gate in practice,
archive it here as a new fixture. The corpus only grows.

Usage: python3 hooks/tests/replay/run.py [--list]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOKS = HERE.parents[1]
FIXTURES = HERE / "fixtures"
LEDGER_HOOK = HOOKS / "verify-ledger.py"
STOP_HOOK = HOOKS / "stop-verify-gate.py"

# Anti-gaming floor: fixtures can be added, never silently removed.
CORPUS_FLOOR = 5

EXAMPLE_CWD = "/workspace/example-project"


def run_hook(hook: Path, payload: dict, state_dir: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("FABLE_GATE_OFF", None)
    env.pop("FABLE_GATE_PILOT", None)
    env.pop("FABLE_SESSION_NAME", None)
    env["FABLE_STATE_DIR"] = state_dir
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def blocked(r: subprocess.CompletedProcess) -> bool:
    for line in (r.stdout or "").strip().splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("decision") == "block":
            return True
    return False


def replay(fixture: dict, state_dir: str) -> bool:
    """Returns True when the gate blocked the scenario (expected outcome)."""
    session = {"session_id": f"replay-{fixture['name']}", "cwd": EXAMPLE_CWD}
    for ev in fixture.get("events", []):
        kind = ev.get("kind")
        if kind == "change":
            payload = {
                **session,
                "tool_name": ev.get("tool", "Edit"),
                "tool_input": {"file_path": ev["file_path"].replace("{CWD}", EXAMPLE_CWD)},
            }
        elif kind == "verify":
            payload = {
                **session,
                "tool_name": "Bash",
                "tool_input": {"command": ev["command"]},
                "tool_response": {
                    "stdout": ev.get("stdout", ""),
                    "exit_code": int(ev.get("exit_code", 0)),
                },
            }
        else:
            raise ValueError(f"unknown event kind: {kind!r}")
        r = run_hook(LEDGER_HOOK, payload, state_dir)
        if r.returncode != 0:
            raise RuntimeError(f"ledger hook failed: {r.stderr}")
    return blocked(run_hook(STOP_HOOK, session, state_dir))


def main() -> int:
    fixtures = sorted(FIXTURES.glob("*.json"))
    if "--list" in sys.argv:
        for f in fixtures:
            print(f.stem)
        return 0
    if len(fixtures) < CORPUS_FLOOR:
        print(
            f"REPLAY FAIL corpus-floor: {len(fixtures)} fixtures < floor {CORPUS_FLOOR} "
            "(fixtures must not be deleted to inflate the rate)"
        )
        return 2
    results: list[tuple[str, bool]] = []
    for f in fixtures:
        fixture = json.loads(f.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="fable-replay-") as td:
            ok = replay(fixture, td)
        results.append((fixture["name"], ok))
        print(f"  {'BLOCKED' if ok else 'MISSED '}  {fixture['name']}")
    n_blocked = sum(1 for _, ok in results if ok)
    rate = 100.0 * n_blocked / len(results)
    print(f"replay: {n_blocked}/{len(results)} blocked ({rate:.1f}%) · corpus={len(results)} (floor {CORPUS_FLOOR})")
    return 0 if n_blocked == len(results) else 2


if __name__ == "__main__":
    sys.exit(main())
