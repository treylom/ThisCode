#!/usr/bin/env python3
"""Memory §5 scorer and hook helpers.

Shared by Claude hooks and Codex Discord bridge. Fail-open by default: command
errors should not break the agent surface.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

PLUS2 = [
    "지난번",
    "전에 했던",
    "이전 방식",
    "예전",
    "원래대로",
    "기존 회의",
    "재발",
    "매번",
    "이번에도",
    "또 같은",
]
WEAK = ["다시", "또", "아까", "원래", "기존"]
TASK = [
    "수정",
    "고쳐",
    "이어",
    "계속",
    "복원",
    "비슷하게",
    "반영",
    "재현",
    "회귀",
    "회의",
    "자료",
    "슬라이드",
    "봇",
    "훅",
]
HIGH_RISK = ["회의", "재발", "매번", "이전 산출", "기존 구현"]

MEMORY_ROOT_HINTS = (
    "memory",
    ".claude-memory",
    "shared",
    "SHARED-INDEX",
    "Second_Brain",
    "AI_Second_Brain",
    "obsidian-ai-vault",
    "Library/",
)


def _read_stdin_json() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def score_prompt(prompt: str) -> dict[str, Any]:
    text = _norm(prompt)
    score = 0
    hits: list[dict[str, Any]] = []

    for phrase in PLUS2:
        if phrase in text:
            score += 2
            hits.append({"phrase": phrase, "points": 2})

    weak_hit = False
    for phrase in WEAK:
        if phrase in text:
            weak_hit = True
            score += 1
            hits.append({"phrase": phrase, "points": 1})

    task_hit = False
    for phrase in TASK:
        if phrase in text:
            task_hit = True
            hits.append({"phrase": phrase, "points": 0})

    if weak_hit and task_hit:
        score += 1
        hits.append({"phrase": "task-term", "points": 1})

    trigger = score >= 2
    first_hit = hits[0]["phrase"] if hits else ""
    query = suggest_query(text, str(first_hit))
    high = any(k in text for k in HIGH_RISK)
    targets = "shared,wd,vault" if high else "shared,wd"
    return {
        "trigger": trigger,
        "score": score,
        "hits": hits,
        "query": query,
        "targets": targets,
        "high_risk": high,
    }


def suggest_query(text: str, phrase: str = "") -> str:
    text = _norm(re.sub(r"<[^>]+>", " ", text))
    if not text:
        return ""
    idx = text.find(phrase) if phrase else -1
    if idx < 0:
        return text[:120]
    start = max(0, idx - 50)
    end = min(len(text), idx + len(phrase) + 70)
    return text[start:end].strip()


def reminder(prompt: str) -> str:
    result = score_prompt(prompt)
    query = result["query"]
    targets = result["targets"]
    return (
        "<system-reminder>\n"
        "MEMORY §5 TRIGGERED: 작업 전 memory search를 먼저 수행하라.\n"
        f"- Required targets: {targets} (shared memory는 항상 포함)\n"
        f"- Suggested query: \"{query}\"\n"
        "- 완료 답변 전 marker를 남겨라: "
        f"memory checked: <path-or-no-hit> | targets={targets} | query=\"{query}\"\n"
        "- no-hit은 성공이다. 없는 기억을 만들지 말고 no-hit으로 attestation하라.\n"
        "</system-reminder>"
    )


def user_prompt_submit() -> int:
    payload = _read_stdin_json()
    prompt = str(payload.get("prompt") or payload.get("message") or "")
    result = score_prompt(prompt)
    if not result["trigger"]:
        return 0
    _append_event_log("preprompt-fire", {"query": result["query"], "targets": result["targets"], "score": result["score"]})
    out = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": reminder(prompt),
        }
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


def _append_event_log(kind: str, data: dict[str, Any]) -> None:
    try:
        path = Path.home() / "obsidian-ai-vault/.claude/state/memory-s5/events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.time(), "kind": kind, **data}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def bridge_reminder_text(prompt: str) -> str:
    result = score_prompt(prompt)
    return reminder(prompt) if result["trigger"] else ""


def _iter_transcript(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except OSError:
        return


def _content_blob(content: Any) -> str:
    return json.dumps(content, ensure_ascii=False) if not isinstance(content, str) else content


def _cmd_has_memory_evidence(cmd: str) -> bool:
    low = cmd.lower()
    if "obsidian-cli" in low and re.search(r"\b(search|read)\b", low):
        return True
    if re.search(r"(^|[;&|()\s])(?:rg|grep|find)\b", cmd) and any(h in cmd for h in MEMORY_ROOT_HINTS):
        return True
    if re.search(r"(^|[;&|()\s])cat\b", cmd) and any(h in cmd for h in MEMORY_ROOT_HINTS):
        return True
    if "vault-search" in low or "shared-index" in low:
        return True
    return False


def _tool_has_memory_evidence(name: str, inp: dict[str, Any]) -> bool:
    lname = name.lower()
    blob = json.dumps(inp, ensure_ascii=False)
    if name == "Bash":
        return _cmd_has_memory_evidence(str(inp.get("command", "")))
    if name in {"Read", "Grep", "Glob"} and any(h in blob for h in MEMORY_ROOT_HINTS):
        return True
    if ("mcp" in lname or "vault" in lname or "obsidian" in lname) and (
        "search" in lname or "read" in lname or "grep" in lname
    ):
        return True
    return False


def _marker_status(blob: str) -> tuple[bool, bool]:
    blob = blob.replace('\\"', '"')
    m = re.search(r"memory checked:\s*(.+)", blob, re.I)
    if not m:
        return False, False
    marker_line = m.group(1)
    valid = bool(re.search(r"targets\s*=\s*[^|\n]+", marker_line) and re.search(r"query\s*=\s*\"[^\"]+\"", marker_line))
    return True, valid


def _bridge_evidence() -> bool:
    paths = []
    if os.environ.get("MEMORY_S5_BRIDGE_LOG"):
        paths.append(Path(os.environ["MEMORY_S5_BRIDGE_LOG"]))
    paths.append(Path.home() / "obsidian-ai-vault/.claude/state/memory-s5/bridge-evidence.jsonl")
    paths.append(Path.home() / ".claude/state/memory-s5/bridge-evidence.jsonl")
    cutoff = time.time() - 6 * 3600
    for path in paths:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                obj = json.loads(line)
                if obj.get("evidence") and float(obj.get("ts", 0)) >= cutoff:
                    return True
        except Exception:
            continue
    return False


def stop_guard() -> int:
    payload = _read_stdin_json()
    if payload.get("stop_hook_active") is True:
        return 0
    transcript = str(payload.get("transcript_path") or "")
    if not transcript:
        return 0

    triggered = False
    marker_seen = False
    marker_valid = False
    evidence = False

    for msg in _iter_transcript(transcript):
        content = (msg.get("message") or {}).get("content")
        blob = _content_blob(content)
        if "MEMORY §5 TRIGGERED" in blob:
            triggered = True
        if msg.get("type") == "user" and score_prompt(blob)["trigger"]:
            triggered = True
        seen, valid = _marker_status(blob)
        marker_seen = marker_seen or seen
        marker_valid = marker_valid or valid
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if _tool_has_memory_evidence(str(block.get("name", "")), block.get("input", {}) or {}):
                        evidence = True

    if not triggered:
        return 0

    bridge_ok = _bridge_evidence()
    reason = ""
    if not marker_seen:
        reason = "memory §5 trigger가 있었지만 `memory checked:` marker가 없습니다."
    elif not marker_valid:
        reason = "`memory checked:` marker 형식이 불완전합니다. `targets=`와 `query=\"...\"`를 포함하세요."
    elif not evidence and not bridge_ok:
        reason = "`memory checked:` marker는 있으나 transcript와 bridge log 양쪽에 memory search evidence가 0회입니다."

    if not reason:
        return 0

    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    "[memory §5 hard hook] "
                    + reason
                    + " 작업 전 shared memory + (WD 또는 vault) search를 수행하고, "
                    + "`memory checked: <path-or-no-hit> | targets=shared,wd|shared,wd,vault | query=\"...\"` marker를 남기세요. "
                    + "no-hit은 성공입니다."
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


def score_cli(text: str) -> int:
    print(json.dumps(score_prompt(text), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("user-prompt-submit")
    sub.add_parser("stop-guard")
    s = sub.add_parser("score")
    s.add_argument("text")
    r = sub.add_parser("bridge-reminder")
    r.add_argument("text")
    args = parser.parse_args()

    if args.cmd == "user-prompt-submit":
        return user_prompt_submit()
    if args.cmd == "stop-guard":
        return stop_guard()
    if args.cmd == "score":
        return score_cli(args.text)
    if args.cmd == "bridge-reminder":
        text = bridge_reminder_text(args.text)
        if text:
            print(text)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
