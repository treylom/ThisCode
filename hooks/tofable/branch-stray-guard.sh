#!/bin/bash
# branch-stray-guard.sh — warn when auto-committed knowledge files land on a
# non-default branch ("branch stray" class).
#
# The failure class: a shared repo holds both code and knowledge/notes
# directories, and an unattended auto-commit (e.g. a session stop hook that
# runs `git add -A && git commit`) fires while the repo happens to be checked
# out on someone's feature branch. Knowledge files written by *other* agents
# get committed onto that branch, vanish from the default branch's history,
# and later look like deletions ("the file existed — now it's gone").
# Detection is cheap at commit time and expensive afterwards, so: warn early.
#
# Usage — call right before an unattended commit while changes are staged:
#   ./branch-stray-guard.sh            # prints warnings, always exits 0
#
# Env:
#   STRAY_GUARD_MAIN="master main"     # branches considered "home" (default)
#   STRAY_GUARD_RE='(^|/)(docs|notes|meetings)/.*\.md$'
#                                      # staged paths to guard (default shown)
#   STRAY_GUARD_OFF=1                  # disable
#
# Warn-only by design: blocking an unattended commit would silently drop
# work; a loud warning plus the guarded-file list gives a recovery breadcrumb
# (git log --all will find them — check the branch axis before declaring a
# file "gone").
set -u
[ "${STRAY_GUARD_OFF:-0}" = "1" ] && exit 0
command -v git >/dev/null 2>&1 || exit 0
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" || exit 0
[ -n "$BRANCH" ] || exit 0

MAIN="${STRAY_GUARD_MAIN:-master main}"
for b in $MAIN; do
  [ "$BRANCH" = "$b" ] && exit 0
done

RE="${STRAY_GUARD_RE:-(^|/)(docs|notes|meetings)/.*\.md$}"
STRAYS="$(git diff --cached --name-only 2>/dev/null | grep -E "$RE" || true)"
[ -n "$STRAYS" ] || exit 0

CNT="$(printf '%s\n' "$STRAYS" | wc -l | tr -d ' ')"
echo "WARN branch-stray-guard: ${CNT} knowledge file(s) staged for commit on non-default branch '${BRANCH}'." >&2
echo "WARN these will be absent from the default branch until merged/cherry-picked:" >&2
printf '%s\n' "$STRAYS" | head -10 | sed 's/^/  WARN  /' >&2
exit 0
