#!/usr/bin/env python3
"""prompt-advance-gate 3-tier tests (nominal/deep/boundary).

Run: python3 hooks/tests/test_prompt_advance_gate.py
Contract: after a requirement-crystallizing marker (interview / brainstorm /
ExitPlanMode) with no prompt-engineering evidence AFTER it, the first
execution-grade call is denied ONCE; the retry passes. Sessions without
markers never trigger. Deny = stdout hookSpecificOutput.permissionDecision.
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
GATE = HOOKS / "prompt-advance-gate.py"
EXAMPLE_CWD = "/workspace/example-project"


def run_hook(payload: dict, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for key in ("FABLE_GATE_OFF", "FABLE_GATE_PILOT", "FABLE_SESSION_NAME"):
        env.pop(key, None)
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(GATE)], input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=30
    )


def denied(proc: subprocess.CompletedProcess) -> bool:
    if not proc.stdout.strip():
        return False
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False
    return out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def write_transcript(directory: Path, lines: list[str]) -> Path:
    path = directory / "transcript.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


INTERVIEW_LINE = json.dumps({"type": "assistant", "text": "Skill invoked: ouroboros:interview crystallized the task"})
PLAN_LINE = json.dumps({"type": "assistant", "text": "ExitPlanMode approved the plan"})
PROMPT_LINE = json.dumps({"type": "assistant", "text": "loaded prompt-engineering-guide.md section for research template"})
CHAT_LINE = json.dumps({"type": "user", "text": "just fix the typo in the readme"})


class PromptAdvanceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.env = {"FABLE_STATE_DIR": str(self.dir / "state")}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def payload(self, transcript: Path, tool: str = "Write") -> dict:
        return {
            "session_id": "s-prompt-gate",
            "cwd": EXAMPLE_CWD,
            "tool_name": tool,
            "tool_input": {"file_path": f"{EXAMPLE_CWD}/app.py", "content": "x"},
            "transcript_path": str(transcript),
        }

    def test_no_marker_never_triggers(self):  # nominal: trivial session
        transcript = write_transcript(self.dir, [CHAT_LINE])
        self.assertFalse(denied(run_hook(self.payload(transcript), self.env)))

    def test_interview_without_prompt_pass_denies_once(self):  # nominal: the contract
        transcript = write_transcript(self.dir, [INTERVIEW_LINE, CHAT_LINE])
        first = run_hook(self.payload(transcript), self.env)
        self.assertTrue(denied(first), first.stdout)
        retry = run_hook(self.payload(transcript), self.env)
        self.assertFalse(denied(retry), "retry after the single bounce must pass")

    def test_prompt_pass_after_marker_allows(self):  # nominal: compliant flow
        transcript = write_transcript(self.dir, [INTERVIEW_LINE, PROMPT_LINE])
        self.assertFalse(denied(run_hook(self.payload(transcript), self.env)))

    def test_prompt_pass_before_marker_still_denies(self):  # deep: ordering matters
        transcript = write_transcript(self.dir, [PROMPT_LINE, PLAN_LINE, CHAT_LINE])
        self.assertTrue(denied(run_hook(self.payload(transcript), self.env)))

    def test_non_gated_tool_ignored(self):  # boundary: Bash/Read are not execution-grade here
        transcript = write_transcript(self.dir, [INTERVIEW_LINE])
        self.assertFalse(denied(run_hook(self.payload(transcript, tool="Bash"), self.env)))

    def test_gate_off_kill_switch(self):  # boundary: kill switch respected
        transcript = write_transcript(self.dir, [INTERVIEW_LINE])
        env = dict(self.env)
        env["FABLE_GATE_OFF"] = "1"
        self.assertFalse(denied(run_hook(self.payload(transcript), env)))

    def test_missing_transcript_fails_open(self):  # boundary: fail-open
        payload = self.payload(self.dir / "nope.jsonl")
        self.assertFalse(denied(run_hook(payload, self.env)))


if __name__ == "__main__":
    unittest.main(verbosity=1)
