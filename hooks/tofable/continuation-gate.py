#!/usr/bin/env python3
"""Stop — continuation gate (deferral-language check).

The mechanical half of rules/continuation.md: if the turn's final assistant
message declares an early stop or deferral ("I'll finish this tomorrow",
"wrapping up here", "다음 세션에 이어서") the gate bounces the Stop once and
asks the three continuation questions — real blocker? whose call? reported?
A deliberate, user-approved stop passes on the next attempt (bounce is
capped at MAX_CONTINUATION_BLOCKS per session). Fail-open on any exception,
same kill switch and pilot scoping as the other gates (FABLE_GATE_OFF /
FABLE_GATE_PILOT).

Why a hook and not just the rule: written stop-discipline gets skipped under
exactly the conditions that produce premature stops (long sessions, low
context, end-of-day fatigue). Knowledge isn't enforcement — the gate is.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from fable_lib import gate_enabled, last_assistant_text, load_ledger, read_stdin_json, save_ledger
except Exception:
    sys.exit(0)

MAX_CONTINUATION_BLOCKS = 1

DEFERRAL_PATTERNS = [
    # English: first-person deferral of remaining work
    r"\b(?:i'?ll|we'?ll|will|let'?s)\s+(?:finish|continue|resume|complete|tackle|revisit|do)\b[^.\n]{0,60}\b(?:tomorrow|next\s+(?:session|time|turn)|later)\b",
    r"\b(?:pick|picking)\s+(?:this|it|that)\s+(?:back\s+)?up\s+(?:tomorrow|later|next)\b",
    r"\b(?:stopping|stop)\s+here\s+for\s+(?:now|today|tonight)\b",
    r"\bwrap(?:ping)?\s+(?:this\s+|it\s+)?up\s+(?:here|for\s+(?:now|today|tonight))\b",
    r"\bleave\s+(?:this|the\s+rest|it)\s+for\s+(?:now|later|tomorrow|next\s+session)\b",
    r"\bcall(?:ing)?\s+it\s+(?:a\s+(?:day|night)|here)\b",
    r"\bdefer(?:ring)?\s+(?:this|the\s+rest|it)\b",
    # Korean: compound stop-intent phrases (bare "내일" alone is too noisy)
    r"내일\s*(?:이어|계속|마저|다시|아침에\s*(?:이어|계속|마저|다시))",  # 아침에 alone is noisy ("내일 아침에 회의") — require a trailing deferral verb
    r"다음\s*(?:세션|턴|기회)\s*(?:에|으로)",
    r"오늘은\s*여기까지",
    r"여기서\s*(?:마무리|정리하|멈추)",
    r"나중에\s*(?:이어|계속|마저)",
    r"이월(?:하|했|됨|된|시키|시켜|할)",  # verb-anchored: bare 이월 collides with 이월(February) in dates like "이월 15일"
]
DEFERRAL_RE = re.compile("|".join(DEFERRAL_PATTERNS), re.IGNORECASE)

QUESTIONS = (
    "continuation-gate: your final message reads like an early stop or deferral "
    "with work possibly remaining. Before stopping, answer the three questions "
    "from rules/continuation.md in your response: (1) is this a real technical "
    "blocker — did you check the safety nets that already exist (auto-compaction, "
    "backups, retries)? (2) whose call is it — finishing early or deferring is the "
    "user's decision, not yours; (3) have you reported the blocker explicitly? "
    "If the stop is genuinely the user's instruction or all goals are closed, "
    "say so plainly and stop again — this gate only bounces once."
)


# last_assistant_text moved to fable_lib (shared with stop-verify-gate's
# absence check — both judge the turn's final message).


def main() -> int:
    try:
        input_data: dict[str, Any] = read_stdin_json()
        if not input_data:
            return 0
        if input_data.get("stop_hook_active") is True:
            return 0  # already inside a Stop-hook chain — loop guard
        if not gate_enabled():
            return 0
        transcript = input_data.get("transcript_path") or ""
        text = last_assistant_text(transcript) if transcript else ""
        if not text or not DEFERRAL_RE.search(text):
            return 0
        ledger = load_ledger(input_data)
        blocks = int(ledger.get("continuation_blocks") or 0)
        if blocks >= MAX_CONTINUATION_BLOCKS:
            return 0  # bounced already this session — a re-affirmed stop passes
        ledger["continuation_blocks"] = blocks + 1
        save_ledger(input_data, ledger)
        print(json.dumps({"decision": "block", "reason": QUESTIONS}, ensure_ascii=False))
        return 0
    except Exception:
        return 0  # fail-open


if __name__ == "__main__":
    raise SystemExit(main())
