"""Runtime helpers for the thiscode Hermes plugin.

The active Hermes runtime helper is the session-start contract drift check.
Knowledge management and vault search are supplied by the km plugin, while
the remaining manifest-only ThisCode surfaces are documented as deferred.
"""

import os
import subprocess
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
REPO_ROOT = PLUGIN_DIR.parent

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
