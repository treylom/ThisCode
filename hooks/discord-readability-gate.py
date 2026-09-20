#!/usr/bin/env python3
"""discord-readability-gate.py — PreToolUse gate: enforce a readable shape (line breaks) on outbound Discord messages.

Rule: rules/discord-comms.md §1-c (readability shape).
Target tools: mcp__plugin_discord_discord__reply / edit_message (and the mcp__discord__* aliases); body = tool_input.text
Judgement (character counts = len):
  ① total length ≥ 350 with zero line breaks              → deny  (one solid block)
  ② one line outside a code fence ≥ 300 chars with 5+ " · " → deny  (a dot-joined run belongs in a line-per-item list)
  ③ one line outside a code fence ≥ 600 chars              → deny  (paragraph too long)
Contract: deny = stdout JSON hookSpecificOutput.permissionDecision="deny" + exit 0. Non-target tool / unparsable input = exit 0 (fail-open).
Bypass (only when a line break would change meaning — tables, code; issued by the sender itself):
      python3 discord-readability-gate.py --allow-once "<reason>"  → ~/.claude/state/discord-readability/<bot>.allow-once (TTL 600 s · consumed once · logged)
"""
from __future__ import annotations

import json
import os
import sys
import time

TOOLS = {
    "mcp__plugin_discord_discord__reply",
    "mcp__plugin_discord_discord__edit_message",
    "mcp__discord__reply",
    "mcp__discord__edit_message",
}
TOTAL_MIN = 350
LINE_DOTLIST_MIN = 300
DOTS_MIN = 5
LINE_MAX = 600
ALLOW_ONCE_TTL = 600
DENY = (
    "🚧 Readability gate: {reason}. "
    "Fix the shape and resend — first line = the conclusion in one line → blank line → one item per line (numbered or '-') → ids/hashes/paths in a final block → signature; one paragraph ≤ 3 sentences. "
    "Rule = rules/discord-comms.md §1-c. Only when a line break would change meaning (tables, code): "
    "`python3 hooks/discord-readability-gate.py --allow-once \"<reason>\"` (one use · logged)."
)


def state_dir() -> str:
    """State directory (env var first — used for test isolation)."""
    return os.environ.get("DISCORD_READABILITY_STATE_DIR") or os.path.expanduser("~/.claude/state/discord-readability")


def bot_name() -> str:
    """Bot id = DISCORD_STATE_DIR basename with the discord- prefix stripped (matches sibling gates)."""
    dsd = os.path.basename(os.environ.get("DISCORD_STATE_DIR", "").rstrip("/"))
    return (dsd[len("discord-"):] if dsd.startswith("discord-") else dsd) or "unknown"


def judge(text):
    """(ok, reason, stats) — rules ①②③. Lines inside a code fence (```) are excluded from ②③."""
    if not isinstance(text, str):
        return True, "", {}
    lines = text.split("\n")
    body, infence = [], False
    for ln in lines:
        if ln.strip().startswith("```"):
            infence = not infence
            continue
        if not infence:
            body.append(ln)
    stats = {"chars": len(text), "newlines": len(lines) - 1, "longest_line": max((len(l) for l in body), default=0)}
    if len(text) >= TOTAL_MIN and stats["newlines"] == 0:
        return False, f"① no line break in {len(text)} chars", stats
    for l in body:
        dots = l.count(" · ")
        if len(l) >= LINE_DOTLIST_MIN and dots >= DOTS_MIN:
            return False, f"② {dots} ' · ' separators on one {len(l)}-char line", stats
        if len(l) >= LINE_MAX:
            return False, f"③ one line is {len(l)} chars ≥ {LINE_MAX}", stats
    return True, "", stats


def _log(row: dict) -> None:
    """Append one row to log.jsonl (failures ignored)."""
    try:
        os.makedirs(state_dir(), exist_ok=True)
        with open(os.path.join(state_dir(), "log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def consume_allow_once(bot: str):
    """Return the reason and delete <bot>.allow-once if within TTL, else None."""
    p = os.path.join(state_dir(), f"{bot}.allow-once")
    try:
        with open(p, encoding="utf-8") as f:
            rec = json.load(f)
        if time.time() - float(rec.get("ts", 0)) <= ALLOW_ONCE_TTL:
            os.remove(p)
            return rec.get("reason") or "(no reason given)"
        os.remove(p)
    except Exception:
        return None
    return None


def issue_allow_once(reason: str) -> str:
    """CLI: issue an allow-once."""
    os.makedirs(state_dir(), exist_ok=True)
    p = os.path.join(state_dir(), f"{bot_name()}.allow-once")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"ts": time.time(), "reason": reason, "by": bot_name()}, f, ensure_ascii=False)
    _log({"ts": time.time(), "bot": bot_name(), "event": "allow-once-issued", "reason": reason})
    return p


def main() -> int:
    """PreToolUse entry point."""
    if len(sys.argv) >= 2 and sys.argv[1] == "--allow-once":
        reason = " ".join(sys.argv[2:]).strip()
        if not reason:
            sys.stderr.write("usage: --allow-once <reason>\n")
            return 2
        print(f"allow-once issued: {issue_allow_once(reason)}")
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") not in TOOLS:
        return 0
    text = (payload.get("tool_input") or {}).get("text")
    ok, reason, stats = judge(text)
    if ok:
        return 0
    bot = bot_name()
    why = consume_allow_once(bot)
    if why:
        _log({"ts": time.time(), "bot": bot, "event": "bypass", "reason": why, "stats": stats})
        return 0
    _log({"ts": time.time(), "bot": bot, "event": "deny", "why": reason, "stats": stats})
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": DENY.format(reason=reason),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
