#!/usr/bin/env python3
"""PreToolUse (Write|Edit|MultiEdit|Task|Agent) — prompt-advance gate.

Workflow contract (owner decision 2026-07-08, interview 2-A "hard"):
    interview / brainstorm / plan  ->  role confirmed
        ->  prompt-engineering pass (/prompt or equivalent)
        ->  execute.

This gate enforces the third step ONCE per session: when the session
transcript shows a requirement-crystallizing phase happened (ouroboros
interview, brainstorming skill, plan mode exit) but NO prompt-engineering
evidence appears after it, the first execution-grade tool call (file
mutation or subagent dispatch) is bounced with a reminder. The identical
retry passes — the gate is a speed bump that makes skipping deliberate,
not a wall (MAX 1 bounce per session).

Natural exemptions:
- sessions with no interview/plan markers (trivial work) never trigger;
- automation/headless sessions are skipped (same convention as the other
  gates: CLAUDE_AUTOMATION / FABLE_GATE_OFF / FABLE_GATE_PILOT);
- fail-open on any exception.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from fable_lib import gate_enabled, load_ledger, read_stdin_json, save_ledger
except Exception:
    sys.exit(0)

GATED_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Task", "Agent"}

# Requirement-crystallizing phase happened:
ROLE_CONFIRM_RE = re.compile(
    r"ouroboros[:_]interview|ouroboros_interview|skill.{0,40}interview"
    r"|superpowers:brainstorming|\"skill\"\s*:\s*\"brainstorming\""
    r"|ExitPlanMode",
    re.IGNORECASE,
)
# Prompt-engineering pass evidence:
PROMPT_PASS_RE = re.compile(
    r"prompt-engineering-guide|/prompt\b|\"skill\"\s*:\s*\"prompt\""
    r"|prompt\s+--batch|image-prompt|expert-domain-priming",
    re.IGNORECASE,
)

REASON = (
    "prompt-advance-gate: this session crystallized a task (interview/"
    "brainstorm/plan) but no prompt-engineering pass has run since. The "
    "workflow is: role confirmed -> advance the prompt (/prompt or the "
    "prompt-engineering guide: structured prompt, expert priming, research/"
    "fact-check/image templates) -> execute. Run the prompt pass, or if this "
    "task genuinely doesn't need one, repeat the same call — it passes after "
    "this bounce."
)


def transcript_tail(input_data: dict[str, Any], max_bytes: int = 400_000) -> str:
    path = str(input_data.get("transcript_path") or "")
    if not path:
        return ""
    try:
        raw = Path(path).read_bytes()
        return raw[-max_bytes:].decode("utf-8", "replace")
    except OSError:
        return ""


def main() -> int:
    try:
        input_data = read_stdin_json()
        if not input_data:
            return 0
        if str(input_data.get("tool_name") or "") not in GATED_TOOLS:
            return 0
        if not gate_enabled():
            return 0

        ledger = load_ledger(input_data)
        if ledger.get("prompt_gate_bounced"):
            return 0  # MAX 1 per session — retry (or any later call) passes

        tail = transcript_tail(input_data)
        if not tail:
            return 0

        confirm_matches = list(ROLE_CONFIRM_RE.finditer(tail))
        if not confirm_matches:
            return 0  # no crystallizing phase — trivial work, gate silent

        last_confirm = confirm_matches[-1].end()
        if PROMPT_PASS_RE.search(tail, last_confirm):
            return 0  # prompt pass already ran after role confirmation

        ledger["prompt_gate_bounced"] = True
        save_ledger(input_data, ledger)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON,
            }
        }))
        return 0
    except Exception:
        return 0  # fail-open, always


if __name__ == "__main__":
    sys.exit(main())
