#!/usr/bin/env python3
"""fable verification-gate hooks — shared library.

Adapted from fable-ish-codex (Apache-2.0, Pandoll-AI)
scripts/ledger.py / parse_tool_result.py / verify_state.py, ported to run as
Claude Code hooks (PostToolUse + Stop).

Adaptation notes:
- No task classifier ported. Instead a lightweight "harness/code surface"
  heuristic (see HARNESS_SURFACE_RE / CODE_EXTS / CONFIG_EXTS below) decides
  which changed files require verification evidence. Plain docs (e.g. notes,
  markdown content outside the harness surface) are exempt.
- FAILURE_RE deliberately excludes the bare words `failed`/`failure` — an
  earlier version matched those and produced false positives on ordinary
  tool output that merely mentions "failed" in prose.
- Ledger state lives outside the project working tree by default (see
  data_root()) so verification bookkeeping never gets committed or synced
  alongside the project's own content.
- Pilot gate: disabled entirely via FABLE_GATE_OFF=1 (kill switch).
  Optionally scoped to one named session via FABLE_GATE_PILOT=<name>
  together with FABLE_SESSION_NAME=<name> on the session side, so a project
  can pilot the gate on a single bot/session before enabling it broadly.
  With neither env var set, the gate is active for every session.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_STOP_BLOCKS = 2

DEFAULT_LEDGER: dict[str, Any] = {
    "changed_files_seen": False,
    "changed_paths": [],
    "change_kinds": [],
    "verification_commands": [],
    "verification_results": [],
    "failures": [],
    "stop_blocks": 0,
    "event_seq": 0,          # monotonic event counter (code-review feedback — closes the
                              # "verify succeeds, then code changes" ordering bypass)
    "last_gated_seq": 0,     # event_seq of the most recent gated (harness/code) change
    "last_updated": "",
}

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{12,}"),
]

CODE_EXTS = {".py", ".sh", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".rb", ".go", ".rs", ".c", ".cc", ".cpp", ".java", ".swift", ".sql", ".css", ".scss"}
CONFIG_EXTS = {".json", ".jsonc", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".plist"}

# Harness surface = changes here are gated regardless of extension (rules,
# hooks, scripts, skills, commands, agents, and the settings files).
HARNESS_SURFACE_RE = re.compile(r"(^|/)\.claude/(hooks|scripts|skills|rules|commands|agents)/|(^|/)settings(\.local)?\.json$")

VERIFY_RE = re.compile(
    r"(?i)\b("
    r"pytest|unittest|go\s+test|cargo\s+test|npm\s+test|pnpm\s+test|yarn\s+test|vitest|jest|playwright|"
    r"lint|eslint|ruff|flake8|mypy|pyright|tsc|typecheck|"
    r"bash\s+-n|zsh\s+-n|sh\s+-n|py_compile|json\.tool|python3?\s+-m\s+unittest|tests?/test_[a-z0-9_]+\.py|"
    r"build|check|validate|verify|diff|shasum|md5|grep\s+-c|wc\s+-l|curl"
    r")\b"
)
DIRECT_TEST_RE = re.compile(r"(?i)(pytest|unittest|vitest|jest|playwright|go\s+test|cargo\s+test)")
# bare `failed|failure` intentionally excluded — see module docstring.
FAILURE_RE = re.compile(
    r"(?i)(command not found|no such file or directory|traceback|syntaxerror|"
    r"\berror:|\b[1-9][0-9]*\s+errors?\b|exit code\s*:?\s*[1-9]|exited with code\s*:?\s*[1-9]|"
    r"tests? failed|build failed|lint failed|assertion(?:error)? failed)"
)
EXIT_ZERO_RE = re.compile(r"(?i)\b(exit code|exited with code|process exited with code)\s*:?\s*0\b")
SUCCESS_RE = re.compile(r"(?i)\b(passed|success(?:fully)?|succeeded|0 failed|compiled successfully|built successfully|build succeeded|ok|green|valid)\b")
MUTATING_BASH_RE = re.compile(r"(?i)\b(chmod|mkdir|mv|cp|rm|touch|tee|sed\s+-i|launchctl|npm\s+run\s+build|git\s+(add|commit|push|reset))\b")
SUCCESS_STATUSES = {"success", "succeeded", "completed", "complete", "ok", "passed", "pass"}
FAILURE_STATUSES = {"failed", "failure", "error", "errored", "fatal", "timeout", "timed_out"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def redact(text: Any, limit: int = 500) -> str:
    value = "" if text is None else str(text)
    value = value.replace("\r", " ").replace("\n", " ").strip()
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    if len(value) > limit:
        return value[: limit - 3] + "..."
    return value


def data_root() -> Path:
    """Ledger storage root.

    Override with FABLE_STATE_DIR. Default: XDG_STATE_HOME (or
    ~/.local/state if unset) / fable-work / ledger — i.e. outside any
    project working tree by default.
    """
    env = os.environ.get("FABLE_STATE_DIR")
    if env:
        base = Path(env).expanduser()
    else:
        xdg = os.environ.get("XDG_STATE_HOME")
        state_home = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "state"
        base = state_home / "fable-work" / "ledger"
    return base.resolve()


def ledger_key(input_data: dict[str, Any]) -> str:
    cwd = input_data.get("cwd") or os.getcwd()
    session_id = input_data.get("session_id") or "no-session"
    return hashlib.sha256(f"{session_id}|{cwd}".encode("utf-8", "replace")).hexdigest()[:24]


def ledger_path(input_data: dict[str, Any]) -> Path:
    return data_root() / "ledgers" / f"{ledger_key(input_data)}.json"


def default_ledger() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_LEDGER)


def load_ledger(input_data: dict[str, Any]) -> dict[str, Any]:
    path = ledger_path(input_data)
    if not path.exists():
        return default_ledger()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_ledger()  # corrupt ledger = fresh ledger (fail-open)
    ledger = default_ledger()
    if isinstance(data, dict):
        ledger.update({key: data.get(key, value) for key, value in ledger.items()})
    for key in ("changed_paths", "change_kinds", "verification_commands", "verification_results", "failures"):
        if not isinstance(ledger.get(key), list):
            ledger[key] = []
    for key in ("event_seq", "last_gated_seq", "stop_blocks"):
        if not isinstance(ledger.get(key), int):
            ledger[key] = 0
    return ledger


def save_ledger(input_data: dict[str, Any], ledger: dict[str, Any]) -> Path:
    path = ledger_path(input_data)
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger["last_updated"] = utc_now()
    # trim
    for key in ("changed_paths", "change_kinds"):
        seen: list[str] = []
        for v in ledger.get(key, []):
            if v not in seen:
                seen.append(v)
        ledger[key] = seen[:40]
    for key in ("verification_commands", "verification_results", "failures"):
        ledger[key] = ledger.get(key, [])[-40:]
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(ledger, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
    return path


def add_unique(ledger: dict[str, Any], key: str, values: list[str]) -> None:
    existing = list(ledger.get(key, []))
    for value in values:
        if value and value not in existing:
            existing.append(value)
    ledger[key] = existing


def classify_path_kind(path_value: str) -> str:
    """harness > code > config > docs/other. Harness surface is gated regardless of extension."""
    p = path_value.replace("\\", "/")
    if HARNESS_SURFACE_RE.search(p):
        return "harness"
    suffix = Path(p).suffix.lower()
    if suffix in CODE_EXTS:
        return "code"
    if suffix in CONFIG_EXTS:
        return "config"
    return "docs"  # plain notes/docs/other = exempt kind


def read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def response_text(value: Any, limit: int = 4000) -> str:
    parts: list[str] = []

    def walk(item: Any) -> None:
        if len(" ".join(parts)) > limit:
            return
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            for key in ("stdout", "stderr", "output", "message", "text", "content", "error", "summary"):
                if key in item:
                    walk(item[key])
            if not parts:
                for child in item.values():
                    walk(child)
        elif isinstance(item, list):
            for child in item[:20]:
                walk(child)

    walk(value)
    return redact(" ".join(parts), limit)


def command_from_input(input_data: dict[str, Any]) -> str:
    tool_input = input_data.get("tool_input")
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or "")
    if isinstance(tool_input, str):
        return tool_input
    return ""


def exit_success(input_data: dict[str, Any], text: str) -> bool | None:
    for candidate in (input_data, input_data.get("tool_response")):
        if isinstance(candidate, dict):
            for key in ("success", "ok"):
                if isinstance(candidate.get(key), bool):
                    return bool(candidate[key])
            for key in ("exit_code", "exitCode", "returncode", "status"):
                value = candidate.get(key)
                if isinstance(value, int):
                    return value == 0
                if isinstance(value, str) and value.isdigit():
                    return int(value) == 0
                if isinstance(value, str):
                    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
                    if normalized in SUCCESS_STATUSES:
                        return True
                    if normalized in FAILURE_STATUSES:
                        return False
    if EXIT_ZERO_RE.search(text):
        return True
    if FAILURE_RE.search(text):
        return False
    if SUCCESS_RE.search(text):
        return True
    return None


def changed_paths(input_data: dict[str, Any]) -> list[str]:
    tool_name = str(input_data.get("tool_name") or "")
    tool_input = input_data.get("tool_input")
    paths: list[str] = []
    if isinstance(tool_input, dict):
        fp = tool_input.get("file_path")
        if fp:
            paths.append(str(fp))
    if tool_name in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:  # MultiEdit — code-review feedback
        return paths or ["edit"]
    return paths


def changed_kinds(input_data: dict[str, Any]) -> list[str]:
    paths = changed_paths(input_data)
    if paths:
        return sorted({classify_path_kind(p.strip()) for p in paths})
    tool_name = str(input_data.get("tool_name") or "")
    if tool_name == "Bash":
        command = command_from_input(input_data)
        # only record mutating bash that touches the harness surface (plain
        # file moves elsewhere stay "docs")
        if MUTATING_BASH_RE.search(command) and HARNESS_SURFACE_RE.search(command):
            return ["harness"]
    return []


def is_verification_command(command: str) -> bool:
    return bool(VERIFY_RE.search(command or ""))


def verification_record(input_data: dict[str, Any]) -> dict[str, Any] | None:
    command = command_from_input(input_data)
    if not command or not is_verification_command(command):
        return None
    text = response_text(input_data.get("tool_response", input_data), 1000)
    success = exit_success(input_data, text)
    return {
        "command": redact(command, 220),
        "success": bool(success) if success is not None else None,
        "summary": redact(text, 220),
    }


def detect_failure(input_data: dict[str, Any]) -> dict[str, Any] | None:
    text = response_text(input_data.get("tool_response", input_data))
    success = exit_success(input_data, text)
    if success is False or (success is None and FAILURE_RE.search(text)):
        return {"kind": "tool-result", "summary": redact(text or command_from_input(input_data), 240)}
    return None


# --- gate decision ---

def gate_enabled() -> bool:
    """Kill-switch + optional pilot scoping (env-based).

    Default: the gate is ACTIVE for every session.
    - FABLE_GATE_OFF=1        — kill switch, disables the gate entirely.
    - FABLE_GATE_PILOT=<name> — optional scoping: when set, the gate only
      activates for sessions whose FABLE_SESSION_NAME matches <name>. Useful
      for piloting the gate on one bot/session before enabling it broadly,
      without hard-coding any project-specific identity check here.
    """
    if os.environ.get("FABLE_GATE_OFF") == "1":
        return False
    pilot = os.environ.get("FABLE_GATE_PILOT", "").strip()
    if not pilot:
        return True
    return os.environ.get("FABLE_SESSION_NAME", "").strip() == pilot


def gated_kinds(ledger: dict[str, Any]) -> set[str]:
    return {k for k in ledger.get("change_kinds", []) if k in {"harness", "code", "config"}}


def has_successful_verification(ledger: dict[str, Any]) -> bool:
    """Only a successful verification **after** the last gated change counts
    (closes the "verify first, then change code" ordering bypass — code-review
    feedback)."""
    last_gated = int(ledger.get("last_gated_seq") or 0)
    return any(
        r.get("success") is True and int(r.get("seq") or 0) >= last_gated
        for r in ledger.get("verification_results", [])
    )


def should_block_stop(ledger: dict[str, Any]) -> tuple[bool, str]:
    stop_blocks = int(ledger.get("stop_blocks") or 0)
    if stop_blocks >= MAX_STOP_BLOCKS:
        return False, ""
    gated = gated_kinds(ledger)
    if not gated:  # no changes, or docs-only = exempt
        return False, ""
    if has_successful_verification(ledger):
        return False, ""
    paths = [p for p in ledger.get("changed_paths", []) if p != "edit"][:5]
    reason = (
        "fable-gate: this turn changed harness/code surface files ("
        + (", ".join(paths) if paths else ", ".join(sorted(gated)))
        + ") but there's no recorded successful verification (test, `bash -n`,\n"
        "grep confirmation, diff, etc.) for it. Run the narrowest verification "
        "that fits the change and confirm the result before stopping. "
        "If no verification is actually possible, say so explicitly in your "
        "response before stopping."
    )
    return True, reason
