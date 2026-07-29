#!/usr/bin/env python3
"""meeting-manifest-gc.py — garbage-collect watchdog manifests of finished meetings.

Why: manifests left at `status: active` after a meeting ends keep feeding
(a) the session-start active-meeting injection, (b) the pre-compact SoT
collection (post-compact re-read list), and (c) compact markers appended to
every active meeting's 02-progress — which keeps refreshing its mtime, so
"recently modified" can never identify a stale meeting. GC must therefore key
on *end signals*, not on recency of the progress file.

Rules (fail-closed — anything unparseable or ambiguous is kept active):
  1. `03-outcome.md` exists in the meeting folder  -> ended  (protocol: writing
     the outcome file is the meeting's end declaration)
  2. manifest file untouched for > STALE_DAYS (default 14) -> ended  (no beat /
     blocked_on update in two weeks = zombie; live meetings keep their manifest
     fresh via watchdog beats)
  3. otherwise, or on parse failure                -> keep
A wrong collection is reversible: re-register with `meeting_watchdog.py start`.

Wired from sessionstart-compact-reread.sh (every SessionStart, fail-open).
Manual: `python3 meeting-manifest-gc.py [--dry-run]`.

Env: MEETING_WATCHDOG_STATE_DIR (default ~/.claude-state) ·
MEETING_PROTOCOL_DIR or BOT_WD (<wd>/meetings) for folder resolution ·
MANIFEST_GC_STALE_DAYS.
"""
import glob
import os
import re
import sys
import time
from datetime import datetime

STATE_DIR = os.environ.get(
    "MEETING_WATCHDOG_STATE_DIR", os.path.expanduser("~/.claude-state")
)
MEET_ROOT = os.environ.get("MEETING_PROTOCOL_DIR", "")
if not MEET_ROOT and os.environ.get("BOT_WD"):
    MEET_ROOT = os.path.join(os.environ["BOT_WD"], "meetings")
STALE_DAYS = float(os.environ.get("MANIFEST_GC_STALE_DAYS", "14"))
DRY = "--dry-run" in sys.argv


def field(txt: str, name: str):
    m = re.search(rf"^{name}:\s*(.+?)\s*$", txt, re.M)
    return m.group(1) if m else None


def resolve_folder(tid, ppath):
    if ppath and os.path.isfile(ppath):
        return os.path.dirname(ppath)
    if not tid or not MEET_ROOT or not os.path.isdir(MEET_ROOT):
        return None
    for d in sorted(glob.glob(os.path.join(MEET_ROOT, "*"))):
        if not os.path.isdir(d):
            continue
        for fn in ("00-context.md", "02-progress.md"):
            p = os.path.join(d, fn)
            try:
                if os.path.isfile(p) and tid in open(p, encoding="utf-8").read():
                    return d
            except OSError:
                pass
    return None


def main():
    now = time.time()
    ended, kept = [], []
    for mf in sorted(glob.glob(os.path.join(STATE_DIR, "meeting-watchdog-*.yaml"))):
        try:
            txt = open(mf, encoding="utf-8").read()
        except OSError:
            continue
        if field(txt, "status") != "active":
            continue
        folder = resolve_folder(field(txt, "thread_id"), field(txt, "progress_path"))
        reason = None
        if folder and os.path.isfile(os.path.join(folder, "03-outcome.md")):
            reason = "outcome"
        elif (now - os.path.getmtime(mf)) > STALE_DAYS * 86400:
            reason = "stale-manifest>%dd" % STALE_DAYS
        if not reason:
            kept.append(os.path.basename(mf))
            continue
        if DRY:
            ended.append((os.path.basename(mf), reason))
            continue
        new = re.sub(r"^status:\s*active\s*$", "status: ended", txt, count=1, flags=re.M)
        if new == txt:  # substitution failed -> keep (fail-closed)
            kept.append(os.path.basename(mf))
            continue
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new = new.rstrip("\n") + f"\nended_by: manifest-gc({reason}) {stamp}\n"
        open(mf, "w", encoding="utf-8").write(new)
        ended.append((os.path.basename(mf), reason))
    print(f"gc: ended={len(ended)} kept-active={len(kept)}" + (" (dry-run)" if DRY else ""))
    for name, reason in ended:
        print(f"  ended {name} [{reason}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
