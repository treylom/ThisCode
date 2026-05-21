#!/usr/bin/env python3
"""meeting_watchdog.py — orchestrator meeting progress watchdog.

Spec: docs/superpowers/specs/2026-05-16-orchestrator-watchdog-design.md

When a meeting thread is created the orchestrator MUST start a watchdog.
A YAML manifest is the single source of truth. Every ~5 min a launchd
ticker (--check) enforces cadence + liveness + termination. The
orchestrator (the only party that can read /goal + TaskList) pushes
current state via --beat. Terminates only when goal_met AND tasks_done.

Source-backed note (claude-code-guide 2026-05-16): Claude Code
`/goal <cond>` is a real built-in (v2.1.139+) but has NO
machine-readable state surface; no periodic hook (Stop fires per-turn).
So an EXTERNAL ticker cannot introspect goal/task state — the in-session
orchestrator pushes it here.

Safety: fail-closed = KEEP ACTIVE (never false-terminate a live meeting);
flock single-flight; atomic manifest writes; idempotent terminate;
Discord post is best-effort (manifest update always wins).
stdlib only.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
STATE_DIR = os.environ.get(
    "MEETING_WATCHDOG_STATE_DIR", os.path.join(HOME, ".claude-state"))
DEFAULT_INTERVAL = 300  # 5 min (operator spec)
STALE_FACTOR = 2        # beats older than INTERVAL*this => liveness warn
DISCORD_API = "https://discord.com/api/v10"
# Optional signature appended to watchdog posts. Empty in a public repo;
# a local runtime may set its persona signature via this env var.
SIGNATURE = os.environ.get("MEETING_WATCHDOG_SIGNATURE", "").strip()
_SIG = f" {SIGNATURE}" if SIGNATURE else ""


def _iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(
        time.time() if ts is None else ts, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now() -> float:
    return time.time()


def _age_sec(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        d = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).total_seconds()
    except ValueError:
        return None


def _manifest_path(thread_id: str) -> str:
    if not re.fullmatch(r"\d{5,25}", thread_id):
        raise SystemExit(f"invalid thread_id: {thread_id!r}")
    return os.path.join(STATE_DIR, f"meeting-watchdog-{thread_id}.yaml")


# --- strict flat-YAML (fail-closed: parse error => caller keeps ACTIVE) ---
class ManifestError(Exception):
    pass


def read_manifest(path: str) -> dict:
    if not os.path.isfile(path):
        raise ManifestError("absent")
    out: dict = {}
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if ":" not in line:
                raise ManifestError(f"bad line {line!r}")
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if not re.fullmatch(r"[a-z_]+", k):
                raise ManifestError(f"bad key {k!r}")
            if v in ("null", ""):
                out[k] = None
            elif v in ("true", "false"):
                out[k] = (v == "true")
            elif re.fullmatch(r"-?\d+", v):
                out[k] = int(v)
            else:
                out[k] = v.strip('"').strip("'")
    return out


_ORDER = ["thread_id", "goal", "created_iso", "check_interval_sec",
          "tasks_total", "tasks_done", "goal_met", "status",
          "last_beat_iso", "last_check_iso", "last_post_iso", "checks",
          "terminate_when"]


def write_manifest(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    lines = ["# meeting watchdog manifest (spec 2026-05-16-orchestrator-"
             "watchdog) — SoT for 'is the watchdog running / done'"]
    keys = _ORDER + [k for k in data if k not in _ORDER]
    for k in keys:
        if k not in data:
            continue
        v = data[k]
        v = ("null" if v is None else "true" if v is True
             else "false" if v is False else str(v))
        lines.append(f"{k}: {v}")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(os.path.dirname(path), os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except OSError:
        pass


class SingleFlight:
    def __init__(self, thread_id):
        self.path = os.path.join(STATE_DIR, f".wd-{thread_id}.lock")
        self.fd = None

    def __enter__(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd)
            self.fd = None
            raise SystemExit("watchdog lock held; no-op")
        return self

    def __exit__(self, *a):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)


def _discord_post(thread_id: str, text: str) -> bool:
    """best-effort; manifest update never depends on this.
    Bot env resolved generically (no hardcoded bot codename in a public
    repo — independent 2-track review): MEETING_WATCHDOG_BOT_ENV override, else the
    running bot's DISCORD_STATE_DIR/.env, else a generic placeholder."""
    env = (os.environ.get("MEETING_WATCHDOG_BOT_ENV")
           or (os.path.join(os.environ["DISCORD_STATE_DIR"], ".env")
               if os.environ.get("DISCORD_STATE_DIR")
               else os.path.join(HOME, ".claude", "channels",
                                 "discord-bot", ".env")))
    tok = None
    try:
        for ln in open(env, encoding="utf-8"):
            ln = ln.strip()
            if ln.startswith("DISCORD_BOT_TOKEN="):
                tok = ln.split("=", 1)[1].strip().strip('"').strip("'")
                break
    except OSError:
        return False
    if not tok:
        return False
    body = json.dumps({"content": text[:1900],
                       "allowed_mentions": {"parse": []}}).encode()
    req = urllib.request.Request(
        f"{DISCORD_API}/channels/{thread_id}/messages", data=body,
        method="POST",
        headers={"Authorization": f"Bot {tok}",
                 "Content-Type": "application/json",
                 "User-Agent": "meeting-watchdog/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (200, 201)
    except (urllib.error.URLError, OSError):
        return False


def cmd_start(a) -> int:
    path = _manifest_path(a.thread_id)
    with SingleFlight(a.thread_id):
        if os.path.isfile(path):
            try:
                m = read_manifest(path)
                if m.get("status") == "active":
                    print("watchdog already active; no-op")
                    return 0
            except ManifestError:
                pass  # corrupt => overwrite with fresh active manifest
        goal_txt = (" ".join(a.goal).strip() if a.goal else "") or "(unset)"
        man = {
            "thread_id": a.thread_id, "goal": goal_txt[:300],
            "created_iso": _iso(), "check_interval_sec": a.interval,
            "tasks_total": a.tasks_total, "tasks_done": 0,
            "goal_met": False, "status": "active",
            "last_beat_iso": _iso(), "last_check_iso": None,
            "last_post_iso": None, "checks": 0,
            "terminate_when": "goal_met AND tasks_done>=tasks_total",
        }
        write_manifest(path, man)
    print(f"watchdog started: {path} (interval={a.interval}s, "
          f"tasks_total={a.tasks_total})")
    return 0


def cmd_beat(a) -> int:
    """orchestrator pushes current goal/task state (it alone can read
    /goal + TaskList). May also be invoked from a Stop hook."""
    path = _manifest_path(a.thread_id)
    with SingleFlight(a.thread_id):
        try:
            man = read_manifest(path)
        except ManifestError:
            print("manifest unreadable; fail-closed (keep active, no-op)")
            return 0
        if man.get("status") == "terminated":
            return 0  # idempotent
        if a.tasks_total is not None:
            man["tasks_total"] = a.tasks_total
        if a.tasks_done is not None:
            man["tasks_done"] = a.tasks_done
        if a.goal_met is not None:
            man["goal_met"] = (a.goal_met == "true")
        man["last_beat_iso"] = _iso()
        write_manifest(path, man)
    return 0


def _terminal(man: dict) -> bool:
    tt = man.get("tasks_total")
    td = man.get("tasks_done")
    return bool(man.get("goal_met")) and tt is not None and td is not None \
        and isinstance(tt, int) and isinstance(td, int) and td >= tt > 0


def cmd_check(a) -> int:
    """launchd ~5min ticker (and Stop-hook). Enforces cadence + liveness
    + termination. Cannot itself read /goal or TaskList — decides only on
    orchestrator-pushed manifest state. fail-closed = keep active."""
    path = _manifest_path(a.thread_id)
    with SingleFlight(a.thread_id):
        try:
            man = read_manifest(path)
        except ManifestError as e:
            # fail-closed: never terminate on unreadable manifest
            print(f"manifest unreadable ({e}); keep ACTIVE, no termination")
            return 0
        if man.get("status") == "terminated":
            return 0  # idempotent no-op
        man["checks"] = (man.get("checks") or 0) + 1
        man["last_check_iso"] = _iso()
        interval = man.get("check_interval_sec") or DEFAULT_INTERVAL
        if _terminal(man):
            man["status"] = "terminated"
            write_manifest(path, man)  # state first; post is best-effort
            _discord_post(
                a.thread_id,
                f"✅ [watchdog] 회의 종료 조건 충족 — goal_met + "
                f"tasks {man.get('tasks_done')}/{man.get('tasks_total')} "
                f"완료. watchdog terminate (checks={man['checks']}).{_SIG}")
            print("terminated (goal_met AND all tasks complete)")
            return 0
        # not terminal: liveness + throttled progress post
        beat_age = _age_sec(man.get("last_beat_iso"))
        post_age = _age_sec(man.get("last_post_iso"))
        if post_age is None or post_age >= interval:
            stale = (beat_age is not None
                     and beat_age > interval * STALE_FACTOR)
            msg = (f"⏱ [watchdog] 진행 점검 #{man['checks']} — "
                   f"tasks {man.get('tasks_done')}/{man.get('tasks_total')}, "
                   f"goal_met={man.get('goal_met')}.")
            if stale:
                msg += (f" ⚠ 오케스트레이터 beat {int(beat_age)}s 무신호 "
                        f"(>{interval*STALE_FACTOR}s) — 진행 정체 의심.")
            msg += _SIG
            if _discord_post(a.thread_id, msg):
                man["last_post_iso"] = _iso()
        write_manifest(path, man)
    return 0


def cmd_status(a) -> int:
    try:
        man = read_manifest(_manifest_path(a.thread_id))
    except ManifestError as e:
        print(f"unreadable ({e}) — fail-closed treat as ACTIVE")
        return 0
    print(json.dumps(man, ensure_ascii=False, indent=1))
    return 0


def cmd_stop(a) -> int:
    path = _manifest_path(a.thread_id)
    with SingleFlight(a.thread_id):
        try:
            man = read_manifest(path)
        except ManifestError:
            print("nothing to stop (unreadable/absent)")
            return 0
        if man.get("status") == "terminated":
            return 0
        man["status"] = "terminated"
        man["last_check_iso"] = _iso()
        write_manifest(path, man)
    print("watchdog manually stopped (terminated)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="meeting progress watchdog")
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("start")
    s.add_argument("thread_id")
    # nargs="*" so a multi-word goal survives programmatic (launchd /
    # orchestrator) invocation even if the caller does not quote it.
    s.add_argument("--goal", nargs="*", default=[])
    s.add_argument("--tasks-total", type=int, default=0, dest="tasks_total")
    s.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    s.set_defaults(fn=cmd_start)
    b = sub.add_parser("beat")
    b.add_argument("thread_id")
    b.add_argument("--tasks-total", type=int, default=None,
                   dest="tasks_total")
    b.add_argument("--tasks-done", type=int, default=None, dest="tasks_done")
    b.add_argument("--goal-met", choices=["true", "false"], default=None,
                   dest="goal_met")
    b.set_defaults(fn=cmd_beat)
    c = sub.add_parser("check")
    c.add_argument("thread_id")
    c.set_defaults(fn=cmd_check)
    st = sub.add_parser("status")
    st.add_argument("thread_id")
    st.set_defaults(fn=cmd_status)
    sp = sub.add_parser("stop")
    sp.add_argument("thread_id")
    sp.set_defaults(fn=cmd_stop)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
