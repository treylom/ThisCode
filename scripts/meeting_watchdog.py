#!/usr/bin/env python3
"""meeting_watchdog.py — orchestrator meeting progress watchdog.

Spec: docs/superpowers/specs/2026-05-16-orchestrator-watchdog-design.md

When a meeting thread is created the orchestrator MUST start a watchdog.
A YAML manifest is the single source of truth. Every ~5 min a launchd
ticker (--check) enforces cadence + liveness + termination. The
orchestrator (the only party that can read /goal + TaskList) pushes
current state via --beat. Terminates only when goal_met AND tasks_done.

SOURCE FACT (claude-code-guide 2026-05-16): Claude Code `/goal <cond>`
is a real built-in (v2.1.139+) but has NO machine-readable state surface;
no periodic hook (Stop fires per-turn). So an EXTERNAL ticker cannot
introspect goal/task state — the in-session orchestrator pushes it here.

2026-06-03 fix (재경님 "tasks 0/5 고정 + beat 무신호 false alarm + 종료 미인식"):
_parse_progress 의 line_re 가 한 bracket 형식([HH:MM KST MM-DD])만 매칭해서
실제 봇 줄([YYYY-MM-DD ~HH:MM KST] 등)을 0개 파싱 → tasks 영영 0, broken
auto-beat 가 수동 beat 를 0 으로 덮어씀, bot_last(liveness) 산출 후 폐기,
종료 자동인식 부재. → 파서를 bracket 형식 불문 robust 화 + done_re 비앵커 +
auto-beat 는 max(올림만) + bot_last 로 liveness + 회의 종료 마커로 goal_met.

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
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
STATE_DIR = os.environ.get(
    "MEETING_WATCHDOG_STATE_DIR", os.path.join(HOME, ".claude-state"))
DEFAULT_INTERVAL = 300  # 5 min (operator spec)
STALE_FACTOR = 2        # beats older than INTERVAL*this => liveness warn
DISCORD_API = "https://discord.com/api/v10"
KST = timezone(timedelta(hours=9))
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


def _parse_progress(
    progress_path: str,
) -> tuple[int, dict[str, float], bool]:
    """Parse 02-progress.md — robust to the bracket formats bots use in the
    wild (date/time in ANY order, optional year, optional ~):
        [HH:MM KST]                  (hook canonical, 손석희)
        [YYYY-MM-DD HH:MM KST]       (AK-Tofu)
        [YYYY-MM-DD ~HH:MM KST]      (카파시)
        [HH:MM KST MM-DD]            (스트레인지)

    Returns:
        tasks_done: count of unique bot names whose status contains 완료/PASS
        bot_last:   {bot_name: last_post_epoch (float)} — liveness signal
        goal_done:  True if any status carries a closure marker (회의 종료)
    """
    line_re = re.compile(r"\[([^\]]*)\]\s*([^|\n]+?)\s*\|\s*([^|\n]*?)\s*\|")
    done_re = re.compile(r"완료|PASS")                 # CONTAINS (was ^...$)
    term_re = re.compile(r"회의\s*종료|goal[_ ]?met")
    time_re = re.compile(r"(\d{1,2}):(\d{2})")
    date_full_re = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
    date_md_re = re.compile(r"(?<![\d:])(\d{1,2})-(\d{1,2})(?![\d:])")
    done_bots: set[str] = set()
    bot_last: dict[str, float] = {}
    goal_done = False
    now = datetime.now(KST)

    try:
        with open(progress_path, encoding="utf-8") as fh:
            for line in fh:
                m = line_re.search(line)
                if not m:
                    continue
                bracket, bot, status = (g.strip() for g in m.groups())
                tm = time_re.search(bracket)
                epoch = None
                if tm:
                    h, mi = int(tm.group(1)), int(tm.group(2))
                    dfm = date_full_re.search(bracket)
                    if dfm:
                        y, mo, d = (int(dfm.group(1)), int(dfm.group(2)),
                                    int(dfm.group(3)))
                    else:
                        mdm = date_md_re.search(bracket)
                        if mdm:
                            y, mo, d = now.year, int(mdm.group(1)), \
                                int(mdm.group(2))
                        else:
                            y, mo, d = now.year, now.month, now.day
                    try:
                        epoch = datetime(y, mo, d, h, mi, tzinfo=KST).timestamp()
                    except (ValueError, OverflowError):
                        epoch = None
                if epoch is not None and (
                        bot not in bot_last or epoch > bot_last[bot]):
                    bot_last[bot] = epoch
                if done_re.search(status):
                    done_bots.add(bot)
                if term_re.search(status):
                    goal_done = True
    except OSError:
        pass

    return len(done_bots), bot_last, goal_done


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
            "terminate_when": "goal_met (explicit close signal)",
        }
        if getattr(a, "participants", None):
            man["active_participants"] = a.participants
        if getattr(a, "progress_path", None):
            man["progress_path"] = a.progress_path
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
    """Terminate when the orchestrator has explicitly signalled completion:
    goal_met == True (set via --beat --goal-met true, or auto-detected from a
    회의 종료 / goal_met marker in 02-progress). goal_met is the authoritative
    close signal; tasks_done/tasks_total remain a progress DISPLAY (the
    unique-bot proxy need not reach tasks_total). fail-closed: no goal_met =>
    stay ACTIVE (never false-terminate a live, unclosed meeting)."""
    return man.get("goal_met") is True


def cmd_check(a) -> int:
    """launchd ~5min ticker (and Stop-hook). Enforces cadence + liveness
    + termination. Cannot itself read /goal or TaskList — decides only on
    orchestrator-pushed manifest state + 02-progress.md. fail-closed."""
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

        # ⓐ Auto-beat from 02-progress.md: tasks_done + liveness + terminal
        # (no orchestrator hand needed). Robust to bot bracket-format variety.
        progress_path = man.get("progress_path")
        if progress_path and os.path.isfile(progress_path):
            auto_done, bot_last, goal_done = _parse_progress(progress_path)
            # tasks_done: take MAX — never overwrite a higher manual beat down
            # (the old code reset a manual beat to a broken 0).
            if auto_done > (man.get("tasks_done") or 0):
                man["tasks_done"] = auto_done
            # liveness: recent 02-progress activity IS a beat. The meeting is
            # live even if the orchestrator never called --beat. Kills the
            # false "오케스트레이터 beat 무신호" alarm (bot_last was discarded).
            if bot_last:
                latest = max(bot_last.values())
                beat_age = _age_sec(man.get("last_beat_iso"))
                if beat_age is None or (_now() - latest) < beat_age:
                    man["last_beat_iso"] = _iso(latest)
            # completion auto-recognize: orchestrator wrote 회의 종료/goal_met
            if goal_done and not man.get("goal_met"):
                man["goal_met"] = True
                print("auto goal_met: 회의 종료/goal_met marker in 02-progress")

        if _terminal(man):
            man["status"] = "terminated"
            write_manifest(path, man)  # state first; post is best-effort
            _discord_post(
                a.thread_id,
                f"✅ [watchdog] 회의 종료 인식 — goal_met. tasks "
                f"{man.get('tasks_done')}/{man.get('tasks_total')}. "
                f"watchdog terminate (checks={man['checks']}).{_SIG}")
            print("terminated (goal_met — explicit close signal)")
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
                msg += (f" ⚠ {int(beat_age)}s 활동 무신호 "
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
    s.add_argument("--participants", default=None,
                   help="bot:user_id,bot:user_id,... for per-bot liveness")
    s.add_argument("--progress-path", default=None, dest="progress_path",
                   help="absolute path to 02-progress.md for liveness parser")
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
