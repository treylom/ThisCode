#!/bin/bash
# precompact-sot-flush.sh — PreCompact hook (engine #1 of the compact chain).
#
# Fires right before a compaction. A frequent auto-compact (small-context
# models) replaces the live conversation with a summary; if the bot then
# trusts only that summary it (a) loses sight of unsaved work and (b) drifts
# on facts it should re-read from live SoT files. This hook, at that chokepoint:
#   ① collects the files this session edited (parsed from the transcript)
#   ② collects the SoT paths worth re-reading (rules INDEX, active meeting)
#   ③ writes them to a disk sidecar (consumed by SessionStart matcher=compact)
#   ④ optionally flushes edited files to a configured dest (env, opt-in)
# The actual re-read reminder is injected AFTER compaction by
# sessionstart-compact-reread.sh (two-stage: PreCompact stash → SessionStart
# re-inject), because PostCompact cannot inject context.
#
# Contract: PreCompact can block but this hook never does — pure I/O side
# effects then exit 0. payload: .session_id .transcript_path .trigger
#
# Generalization: all paths are env-driven (no maintainer-machine hardcoding).
#   MEETING_RULES_INDEX     — path to the rules INDEX to always re-read (opt).
#   MEETING_PROTOCOL_DIR / BOT_WD — active meeting dir base (opt).
#   MEETING_COMPACT_FLUSH_SRC + _DEST — if both set, rsync edited files
#       under SRC to DEST (mirrors <rel>); else flush is skipped.
# fail-open: any error → exit 0 (compaction proceeds). Automation skips.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/hookkit.sh"
hk_failopen
hk_read_input
hk_is_automation && exit 0

SESSION="$(hk_json '.session_id')"
[ -n "$SESSION" ] || exit 0
SAFE="$(printf '%s' "$SESSION" | tr -c 'A-Za-z0-9_-' '_')"
TRIGGER="$(hk_json '.trigger // empty')"
BOT="$(hk_bot)"
TRANSCRIPT="$(hk_transcript)"

STATE_DIR="${MEETING_WATCHDOG_STATE_DIR:-$HOME/.claude-state}"
mkdir -p "$STATE_DIR" 2>/dev/null || exit 0
SIDECAR="$STATE_DIR/precompact-sot-$SAFE.json"

RULES_INDEX="${MEETING_RULES_INDEX:-}"
FLUSH_SRC="${MEETING_COMPACT_FLUSH_SRC:-}"
FLUSH_DEST="${MEETING_COMPACT_FLUSH_DEST:-}"
MEET_DIR="${MEETING_PROTOCOL_DIR:-}"
[ -z "$MEET_DIR" ] && [ -n "${BOT_WD:-}" ] && MEET_DIR="$BOT_WD/meetings"

# ── ① session-edited files from transcript (bounded tail, Write/Edit/MultiEdit) ──
EDITED=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ] && command -v python3 >/dev/null 2>&1; then
  EDITED="$(TRANSCRIPT="$TRANSCRIPT" python3 - <<'PY' 2>/dev/null || true
import os, json
tp = os.environ["TRANSCRIPT"]
seen = []
try:
    lines = open(tp, encoding="utf-8").read().splitlines()
except OSError:
    raise SystemExit(0)
for ln in lines[-4000:]:
    ln = ln.strip()
    if not ln or '"file_path"' not in ln:
        continue
    try:
        obj = json.loads(ln)
    except Exception:
        continue
    msg = obj.get("message", obj)
    content = msg.get("content") if isinstance(msg, dict) else None
    if not isinstance(content, list):
        continue
    for blk in content:
        if not isinstance(blk, dict):
            continue
        if blk.get("type") == "tool_use" and blk.get("name") in ("Write", "Edit", "MultiEdit"):
            fp = (blk.get("input") or {}).get("file_path", "")
            if fp:
                if fp in seen:
                    seen.remove(fp)
                seen.append(fp)
for fp in seen[-10:]:
    print(fp)
PY
)"
fi

# ── ④ optional flush: edited files under FLUSH_SRC → FLUSH_DEST (mirror <rel>) ──
if [ -n "$FLUSH_SRC" ] && [ -n "$FLUSH_DEST" ] && command -v rsync >/dev/null 2>&1 && [ -n "$EDITED" ]; then
  while IFS= read -r FILE; do
    [ -n "$FILE" ] && [ -f "$FILE" ] || continue
    case "$FILE" in "$FLUSH_SRC"/*) ;; *) continue ;; esac
    REL="${FILE#$FLUSH_SRC/}"
    DEST="$FLUSH_DEST/$REL"
    mkdir -p "$(dirname "$DEST")" 2>/dev/null || continue
    rsync -aL "$FILE" "$DEST" 2>/dev/null && hk_log "precompact flush: $REL"
  done <<< "$EDITED"
fi

# ── ②③ SoT path collection + sidecar write ──
KST="$(hk_now_kst)"
if command -v python3 >/dev/null 2>&1; then
  SIDECAR="$SIDECAR" SESSION="$SESSION" BOT="$BOT" KST="$KST" TRIGGER="$TRIGGER" \
  RULES_INDEX="$RULES_INDEX" MEET_DIR="$MEET_DIR" STATE_DIR="$STATE_DIR" \
  EDITED="$EDITED" python3 - <<'PY' 2>/dev/null || true
import os, json, glob, re
home = os.path.expanduser("~") + "/"
def short(p): return p.replace(home, "~/")

paths = []
def add(p):
    if p and os.path.exists(p) and p not in paths:
        paths.append(p)

add(os.environ.get("RULES_INDEX", ""))

# active meeting threads from watchdog manifests (if state dir present)
threads = []
state = os.environ["STATE_DIR"]; meet = os.environ.get("MEET_DIR", "")
for mf in sorted(glob.glob(os.path.join(state, "meeting-watchdog-*.yaml"))):
    tid = status = None
    try:
        for ln in open(mf, encoding="utf-8"):
            ln = ln.strip()
            if ln.startswith("thread_id:"): tid = ln.split(":", 1)[1].strip()
            elif ln.startswith("status:"):  status = ln.split(":", 1)[1].strip()
    except OSError:
        continue
    if status == "active" and tid and re.fullmatch(r"\d{5,25}", tid):
        threads.append(tid)
        if meet and os.path.isdir(meet):
            for d in sorted(glob.glob(os.path.join(meet, "*"))):
                if not os.path.isdir(d):
                    continue
                for fn in ("02-progress.md", "00-context.md", "01-spec.md"):
                    p = os.path.join(d, fn)
                    try:
                        if os.path.isfile(p) and tid in open(p, encoding="utf-8").read():
                            for fn2 in ("02-progress.md", "00-context.md", "01-spec.md"):
                                add(os.path.join(d, fn2))
                            break
                    except OSError:
                        pass

for fp in (os.environ.get("EDITED", "") or "").splitlines():
    add(fp.strip())

doc = {
    "session_id": os.environ["SESSION"],
    "bot": os.environ.get("BOT", ""),
    "created_kst": os.environ.get("KST", ""),
    "trigger": os.environ.get("TRIGGER", ""),
    "sot_paths": [short(p) for p in paths],
    "meeting_threads": threads,
    "compacted_kst": None,
}
try:
    json.dump(doc, open(os.environ["SIDECAR"], "w", encoding="utf-8"), ensure_ascii=False)
except OSError:
    pass
PY
  hk_log "precompact sidecar: $(basename "$SIDECAR") trigger=${TRIGGER:-?}"
fi

exit 0
