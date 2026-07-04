#!/usr/bin/env python3
"""fable verification-gate 3-tier tests (nominal/deep/boundary).

Run: python3 hooks/tests/test_gate.py
Drives the hooks as real subprocesses (echo JSON | python3 hook.py).
Stop contract = hookkit hk_block_stop convention: on block, stdout JSON
{"decision":"block"} + exit 0 (checked via stdout content, not returncode,
since the hook always exits 0 by design).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
LEDGER_HOOK = HOOKS / "verify-ledger.py"
STOP_HOOK = HOOKS / "stop-verify-gate.py"

# Generic example project root used only inside test payloads — no real filesystem
# access happens at these paths, they just need to look like plausible cwd/file_path
# values for the classifier regexes.
EXAMPLE_CWD = "/workspace/example-project"


def run_hook(hook: Path, payload: dict | str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("FABLE_GATE_OFF", None)
    env.pop("FABLE_GATE_PILOT", None)
    env.pop("FABLE_SESSION_NAME", None)
    env.update(extra_env or {})
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(hook)], input=raw, capture_output=True, text=True, env=env, timeout=30
    )


def blocked(r: subprocess.CompletedProcess) -> bool:
    """Whether stdout carries a decision:block JSON line (current contract)."""
    for line in (r.stdout or "").strip().splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("decision") == "block":
            return True
    return False


class FableGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="fable-ledger-test-")
        # Default env: no pilot scoping configured → gate active by default.
        self.env = {"FABLE_STATE_DIR": self.tmp.name}
        self.session = {"session_id": "test-sess", "cwd": EXAMPLE_CWD}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def ledger_files(self) -> list[Path]:
        d = Path(self.tmp.name) / "ledgers"
        return sorted(d.glob("*.json")) if d.exists() else []

    def record_change(self, file_path: str, tool: str = "Edit") -> None:
        r = run_hook(LEDGER_HOOK, {**self.session, "tool_name": tool, "tool_input": {"file_path": file_path}}, self.env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def record_verify(self, command: str, stdout: str = "OK passed", exit_code: int = 0) -> None:
        r = run_hook(
            LEDGER_HOOK,
            {**self.session, "tool_name": "Bash", "tool_input": {"command": command}, "tool_response": {"stdout": stdout, "exit_code": exit_code}},
            self.env,
        )
        self.assertEqual(r.returncode, 0, r.stderr)

    def stop(self, extra: dict | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
        r = run_hook(STOP_HOOK, {**self.session, **(extra or {})}, env or self.env)
        self.assertEqual(r.returncode, 0, f"contract: always exit 0: {r.stderr}")
        return r

    # ---------- tier 1: nominal ----------
    def test_nominal_change_plus_verify_passes(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/.claude/rules/foo.md")
        self.record_verify("grep -c 'marker' .claude/rules/foo.md", "1", 0)
        self.assertFalse(blocked(self.stop()), "verification after a change should pass")

    def test_nominal_ledger_records_harness_kind_and_seq(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/.claude/hooks/bar.py")
        data = json.loads(self.ledger_files()[0].read_text())
        self.assertTrue(data["changed_files_seen"])
        self.assertIn("harness", data["change_kinds"])
        self.assertGreaterEqual(data["last_gated_seq"], 1)

    # ---------- tier 2: deep (extended behavior) ----------
    def test_deep_change_without_verify_blocks_then_caps(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/.claude/scripts/baz.sh")
        r1 = self.stop()
        self.assertTrue(blocked(r1), "1st stop = block (stdout JSON)")
        self.assertIn("fable-gate", r1.stdout)
        r2 = self.stop()
        self.assertTrue(blocked(r2), "2nd stop = block (cap 2)")
        r3 = self.stop()
        self.assertFalse(blocked(r3), "3rd stop = cap exceeded, passes")

    def test_deep_failed_verification_does_not_satisfy(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/.claude/hooks/x.py")
        self.record_verify("python3 -m unittest x_test", "1 errors FAILED (exit code 1)", 1)
        self.assertTrue(blocked(self.stop()), "only a failed verification should still block")

    def test_deep_verify_before_change_still_blocks(self) -> None:
        """Ordering-bypass guard: 'verify succeeds, then code changes' must not satisfy the gate."""
        self.record_verify("python3 -m unittest old_test", "OK passed", 0)
        self.record_change(f"{EXAMPLE_CWD}/.claude/hooks/after_verify.py")
        self.assertTrue(blocked(self.stop()), "a change after the verification is stale evidence — must block")

    def test_deep_verify_after_change_passes(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/.claude/hooks/y2.py")
        self.record_verify("python3 -m unittest y2_test", "OK passed", 0)
        self.assertFalse(blocked(self.stop()), "verify after change should pass")

    def test_deep_code_file_outside_harness_gated(self) -> None:
        self.record_change("/workspace/some/random/script.py")
        self.assertTrue(blocked(self.stop()), "a code extension is gated regardless of path")

    def test_deep_multiedit_recorded(self) -> None:
        """MultiEdit changes must be recorded just like Edit/Write."""
        self.record_change(f"{EXAMPLE_CWD}/.claude/hooks/me.py", tool="MultiEdit")
        self.assertTrue(blocked(self.stop()), "MultiEdit changes are gated too")

    # ---------- tier 3: boundary ----------
    def test_boundary_stop_hook_active_passes(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/.claude/hooks/y.py")
        self.assertFalse(blocked(self.stop({"stop_hook_active": True})), "stop_hook_active must not re-block")

    def test_boundary_docs_only_exempt(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/docs/notes/plan.md")
        self.assertFalse(blocked(self.stop()), "plain docs/notes markdown = exempt")

    def test_boundary_kill_switch(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/.claude/hooks/z.py")
        self.assertFalse(blocked(self.stop(env={**self.env, "FABLE_GATE_OFF": "1"})), "FABLE_GATE_OFF=1 = passes")

    def test_boundary_pilot_scope_mismatch_passes(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/.claude/hooks/w.py")
        r = self.stop(env={
            "FABLE_STATE_DIR": self.tmp.name,
            "FABLE_GATE_PILOT": "pilot-a",
            "FABLE_SESSION_NAME": "some-other-session",
        })
        self.assertFalse(blocked(r), "pilot scoping configured but this session doesn't match = passes")

    def test_boundary_pilot_scope_match_blocks(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/.claude/hooks/v.py")
        r = self.stop(env={
            "FABLE_STATE_DIR": self.tmp.name,
            "FABLE_GATE_PILOT": "pilot-a",
            "FABLE_SESSION_NAME": "pilot-a",
        })
        self.assertTrue(blocked(r), "matching pilot scope = gate active")

    def test_boundary_corrupt_ledger_fails_open(self) -> None:
        self.record_change(f"{EXAMPLE_CWD}/.claude/hooks/u.py")
        for f in self.ledger_files():
            f.write_text("{corrupt json!!")
        self.assertFalse(blocked(self.stop()), "corrupt ledger = fail-open")

    def test_boundary_empty_stdin_passes(self) -> None:
        for hook in (LEDGER_HOOK, STOP_HOOK):
            r = run_hook(hook, "", self.env)
            self.assertEqual(r.returncode, 0, f"{hook.name}: empty stdin fail-open")
            self.assertFalse(blocked(r))

    def test_boundary_invalid_json_passes(self) -> None:
        for hook in (LEDGER_HOOK, STOP_HOOK):
            r = run_hook(hook, "not-json{{{", self.env)
            self.assertEqual(r.returncode, 0, f"{hook.name}: non-JSON fail-open")
            self.assertFalse(blocked(r))

    def test_boundary_no_change_no_block(self) -> None:
        self.assertFalse(blocked(self.stop()), "0 recorded changes = passes")


if __name__ == "__main__":
    unittest.main(verbosity=1)
