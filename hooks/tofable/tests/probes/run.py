#!/usr/bin/env python3
"""Practice probes — deterministic contract checks for the gate pipeline itself.

Where replay/ asks "does the gate still block past violations?", probes ask
"are the pipeline's *contracts* still alive?" — the invariants that other
tooling (and the operator's trust) depend on. Each probe has a gold
expectation fixed in this file; drift in any contract exits 2 (fail-loud).

Probes:
  P1 ledger-records-change      — a gated Edit lands in the ledger with kind+seq
  P2 ledger-records-verify      — a successful verify command lands with success=True
  P3 stop-contract-exit-zero    — the Stop hook always exits 0 (block is stdout JSON, not returncode)
  P4 block-carries-reason       — a block decision carries a non-empty human reason
  P5 docs-only-exempt           — docs/notes-only changes never block (gate scope contract)
  P6 gate-off-escape-hatch      — FABLE_GATE_OFF=1 disables blocking (operator override contract)

Usage: python3 hooks/tests/probes/run.py
Exit 0 = all probes PASS · exit 2 = any contract broken.
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
LEDGER_HOOK = HOOKS / "verify-ledger.py"
STOP_HOOK = HOOKS / "stop-verify-gate.py"
EXAMPLE_CWD = "/workspace/example-project"


def run_hook(hook: Path, payload: dict, state_dir: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for k in ("FABLE_GATE_OFF", "FABLE_GATE_PILOT", "FABLE_SESSION_NAME"):
        env.pop(k, None)
    env["FABLE_STATE_DIR"] = state_dir
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(hook)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, timeout=30,
    )


def block_lines(r: subprocess.CompletedProcess) -> list[dict]:
    out = []
    for line in (r.stdout or "").strip().splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("decision") == "block":
            out.append(d)
    return out


def ledger_of(state_dir: str) -> dict:
    files = sorted((Path(state_dir) / "ledgers").glob("*.json"))
    return json.loads(files[0].read_text(encoding="utf-8")) if files else {}


SESSION = {"session_id": "probe-sess", "cwd": EXAMPLE_CWD}


def probe_ledger_records_change(td: str) -> bool:
    run_hook(LEDGER_HOOK, {**SESSION, "tool_name": "Edit",
                           "tool_input": {"file_path": f"{EXAMPLE_CWD}/.claude/hooks/p.py"}}, td)
    led = ledger_of(td)
    return "harness" in led.get("change_kinds", []) and int(led.get("last_gated_seq", 0)) >= 1


def probe_ledger_records_verify(td: str) -> bool:
    run_hook(LEDGER_HOOK, {**SESSION, "tool_name": "Bash",
                           "tool_input": {"command": "python3 -m pytest tests/"},
                           "tool_response": {"stdout": "1 passed", "exit_code": 0}}, td)
    results = ledger_of(td).get("verification_results", [])
    return any(r.get("success") is True for r in results)


def probe_stop_contract_exit_zero(td: str) -> bool:
    run_hook(LEDGER_HOOK, {**SESSION, "tool_name": "Edit",
                           "tool_input": {"file_path": f"{EXAMPLE_CWD}/src/q.py"}}, td)
    r = run_hook(STOP_HOOK, SESSION, td)
    return r.returncode == 0 and bool(block_lines(r))


def probe_block_carries_reason(td: str) -> bool:
    run_hook(LEDGER_HOOK, {**SESSION, "tool_name": "Edit",
                           "tool_input": {"file_path": f"{EXAMPLE_CWD}/src/r.py"}}, td)
    blocks = block_lines(run_hook(STOP_HOOK, SESSION, td))
    return bool(blocks) and len(str(blocks[0].get("reason", ""))) > 20


def probe_docs_only_exempt(td: str) -> bool:
    run_hook(LEDGER_HOOK, {**SESSION, "tool_name": "Edit",
                           "tool_input": {"file_path": f"{EXAMPLE_CWD}/notes/journal.md"}}, td)
    return not block_lines(run_hook(STOP_HOOK, SESSION, td))


def probe_gate_off_escape_hatch(td: str) -> bool:
    run_hook(LEDGER_HOOK, {**SESSION, "tool_name": "Edit",
                           "tool_input": {"file_path": f"{EXAMPLE_CWD}/src/s.py"}}, td)
    r = run_hook(STOP_HOOK, SESSION, td, extra_env={"FABLE_GATE_OFF": "1"})
    return r.returncode == 0 and not block_lines(r)


PROBES = [
    ("P1 ledger-records-change", probe_ledger_records_change),
    ("P2 ledger-records-verify", probe_ledger_records_verify),
    ("P3 stop-contract-exit-zero", probe_stop_contract_exit_zero),
    ("P4 block-carries-reason", probe_block_carries_reason),
    ("P5 docs-only-exempt", probe_docs_only_exempt),
    ("P6 gate-off-escape-hatch", probe_gate_off_escape_hatch),
]


def main() -> int:
    failed = 0
    for name, fn in PROBES:
        with tempfile.TemporaryDirectory(prefix="fable-probe-") as td:
            try:
                ok = fn(td)
            except Exception as exc:  # noqa: BLE001 — probe crash = contract broken, fail-loud
                ok, name = False, f"{name} (crashed: {exc})"
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print(f"probes: {len(PROBES) - failed}/{len(PROBES)} PASS")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
