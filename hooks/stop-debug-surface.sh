#!/usr/bin/env bash
# stop-debug-surface.sh — Claude Code Stop hook (DEBUG SURFACE, fail-OPEN)
#
# Maintainer idea (2026-05-18): "stop hook으로 디버깅 진행하는 것도 좋아 보입니다".
#
# SAFETY CONTRACT (the whole reason this is a separate hook):
#   - This hook is **fail-OPEN**. It ALWAYS `exit 0`. It NEVER `exit 2`.
#   - It can therefore NEVER deny session end. (The existing
#     stop-pending-task-check.sh is fail-CLOSED / exit 2 — extending *that*
#     to "debug checks" risks trapping a bot in a non-terminating session.
#     This hook deliberately only *surfaces* state, never blocks.)
#
# Behaviour: on session Stop, if the cwd is a git repo with uncommitted
# changes to tracked source/test files, print a one-line advisory to stderr
# (visible in Claude Code) so debug work isn't silently left unsaved. That's
# it — informational only.
#
# OPT-IN: not auto-registered. Add to ~/.claude/settings.json Stop hooks
# explicitly. Coexists with (does not replace) stop-pending-task-check.sh.
set -uo pipefail

input="$(cat 2>/dev/null || true)"
event=""
active="false"
cwd=""
if command -v jq >/dev/null 2>&1 && [ -n "$input" ]; then
  event="$(jq -r '.hook_event_name // empty' <<<"$input" 2>/dev/null || true)"
  active="$(jq -r '.stop_hook_active // false' <<<"$input" 2>/dev/null || true)"
  cwd="$(jq -r '.cwd // empty' <<<"$input" 2>/dev/null || true)"
fi

# non-Stop event → nothing to do
if [ -n "$event" ] && [ "$event" != "Stop" ]; then
  exit 0
fi
# recursion guard — a Stop hook is already active
if [ "$active" = "true" ]; then
  exit 0
fi

[ -z "$cwd" ] && cwd="$PWD"
cd "$cwd" 2>/dev/null || exit 0

# git repo? (fail-open if not)
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# uncommitted changes to tracked/untracked source|test files
changed="$(git status --porcelain 2>/dev/null \
  | sed 's/^...//' \
  | grep -Ei '\.(sh|mjs|cjs|js|jsx|ts|tsx|py|go|rs|rb|java|c|cc|cpp|h|hpp|json)$' \
  || true)"

if [ -z "$changed" ]; then
  exit 0
fi

n="$(printf '%s\n' "$changed" | grep -c . || true)"
sample="$(printf '%s\n' "$changed" | head -5 | sed 's/^/    /')"

cat >&2 <<EOF

ℹ thiscode stop-debug-surface — 세션 종료: 미커밋 source/test ${n}개 (디버그 작업 미저장일 수 있음)
$sample
(정보 전용 — 본 hook 은 세션 종료를 막지 않습니다. 필요 시 커밋/정리 후 종료 권장.)
EOF
exit 0
