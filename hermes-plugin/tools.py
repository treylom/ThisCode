"""Tool handlers for the thiscode Hermes plugin.

Hermes programmatic search/ingest are DEFERRED (see docs/HERMES-STATUS.md):
thiscode skills are LLM-instruction (SKILL.md), not shell dispatchers, and the
literate-bash `.md.sh` dispatchers were never vendored to the public repo.
Handlers therefore return a structured "deferred" JSON pointing at the
supported Claude Code path. session_start_drift_check (km-version.sh) is real
and stays active. Handlers MUST return JSON strings and MUST NOT raise.
"""

import json
import os
import shlex
import subprocess
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
REPO_ROOT = PLUGIN_DIR.parent

# Programmatic dispatchers are not bundled in this repo (they were never
# vendored, and 1.4.0 moved the km/search skills to the km plugin). These paths
# are intentionally absent so the .exists() guards below always take the
# "deferred" branch — see docs/HERMES-STATUS.md.
SEARCH_DISPATCHER = REPO_ROOT / "hermes-plugin" / "dispatchers" / "tier-implementations.sh"
KM_LITE_CORE = REPO_ROOT / "hermes-plugin" / "dispatchers" / "extract-and-classify.sh"
DRIFT_CHECK = REPO_ROOT / "scripts" / "km-version.sh"


def _run(cmd: list[str], env_extra: dict[str, str] | None = None, timeout: int = 30) -> dict:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env, check=False
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"timeout after {timeout}s", "returncode": -1}
    except FileNotFoundError as exc:
        return {"ok": False, "stdout": "", "stderr": f"missing binary: {exc}", "returncode": -2}


_DEFER = {
    "status": "deferred",
    "reason": "Hermes programmatic dispatch deferred — thiscode skills are LLM-instruction (SKILL.md), not shell dispatchers; the .md.sh dispatcher was not vendored to the public repo.",
    "use_instead": "Claude Code with the km plugin installed: /km:search (or invoke the skill via an LLM agent).",
    "doc": "docs/HERMES-STATUS.md",
}


def _deferred(extra: dict) -> str:
    return json.dumps({**_DEFER, **extra})


def handle_search(args: dict, **_kwargs) -> str:
    query = args.get("query", "").strip()
    if not query:
        return json.dumps({"error": "empty query"})
    env = {}
    if "force_tier" in args:
        env["CLAUDE_DISCODE_FORCE_TIER"] = str(args["force_tier"])
    if not SEARCH_DISPATCHER.exists():
        return _deferred({"query": query})
    res = _run(["bash", str(SEARCH_DISPATCHER), query], env_extra=env)
    return json.dumps({"query": query, **res})


def handle_ingest(args: dict, **_kwargs) -> str:
    cmd: list[str] = ["bash", str(KM_LITE_CORE)]
    for key in ("content", "source", "title"):
        if args.get(key):
            flag = {"content": "--content", "source": "--source-url", "title": "--title"}[key]
            cmd.extend([flag, args[key]])
    if not KM_LITE_CORE.exists():
        return _deferred({"variant": args.get("variant", "lite")})
    res = _run(cmd)
    return json.dumps({"variant": args.get("variant", "lite"), **res})


def session_start_drift_check(*_args, **_kwargs) -> dict:
    """Emit a drift warning to the session if thiscode contracts diverge from the vault mirror."""
    res = _run(["bash", str(DRIFT_CHECK)], timeout=5)
    if not res["ok"]:
        return {
            "context": (
                "thiscode contract drift detected — run `bash {}` for details.".format(DRIFT_CHECK)
            )
        }
    return {}


def cmd_search(args: list[str] | str, **_kwargs) -> str:
    if isinstance(args, list):
        query = " ".join(args)
    else:
        query = str(args)
    return handle_search({"query": query})


def cmd_km(args: list[str] | str, **_kwargs) -> str:
    if isinstance(args, list):
        # primitive parse: --source URL  or  --content "..."
        kv = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--") and i + 1 < len(args):
                kv[args[i][2:]] = args[i + 1]
                i += 2
            else:
                i += 1
        return handle_ingest({"source": kv.get("source"), "content": kv.get("content"), "title": kv.get("title")})
    # single string fallback — treat as inline content
    return handle_ingest({"content": str(args)})
