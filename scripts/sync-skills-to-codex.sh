#!/usr/bin/env bash
# LEGACY. Superseded by the Node installer (cross-platform, zero shell):
#   node bin/thiscode.mjs --apply   # handles Codex skill sync (harness=codex/both)
if command -v node >/dev/null 2>&1; then
  exec node "$(dirname "$0")/../bin/thiscode.mjs" "$@"
fi
echo "[thiscode] Node not found — legacy bash sync (deprecated)" >&2
set -euo pipefail
# sync-skills-to-codex.sh — thiscode
# Expose ThisCode skills (knowledge-manager family etc.) to a Codex CLI agent.
#
# Why: ThisCode is a *Claude Code* plugin (.claude-plugin/) — `/plugin install
# thiscode@thiscode-marketplace` exposes its skills/ to Claude Code. Codex does
# NOT read that. Codex's personal skill scan path is ~/.agents/skills/
# (docs CC↔Codex 1:1 mapping). This script syncs the skill SoT (which stays in
# ThisCode/skills/) into ~/.agents/skills/ so Codex bots can invoke them.
#
# SoT note: ThisCode/skills/ is authoritative. This is a one-way copy
# (ThisCode → ~/.agents/skills). Do not edit the copies.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THISCODE_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_SKILLS="$THISCODE_HOME/skills"
DEST="${CODEX_SKILLS_DIR:-$HOME/.agents/skills}"
LOG="${HOME}/.thiscode-setup.log"

# Skills to sync. KM family first (the documented target); add others as needed.
SKILLS=(knowledge-manager knowledge-manager-lite knowledge-manager-plain knowledge-manager-at knowledge-manager-bootstrap)

# Codex compatibility (allowedTools-derived — see SETUP.md "Codex에서 KM 쓰기"):
#   plain/lite  = supported (no AskUserQuestion; mcp__obsidian optional→fallback)
#   full/bootstrap = degraded (AskUserQuestion-dependent)
#   at          = unsupported (Agent Teams: TeamCreate/SendMessage = Claude-only)
compat() {
  case "$1" in
    knowledge-manager-plain|knowledge-manager-lite) echo "supported" ;;
    knowledge-manager|knowledge-manager-bootstrap)  echo "degraded (AskUserQuestion-dependent)" ;;
    knowledge-manager-at)                           echo "UNSUPPORTED (Agent Teams = Claude Code only)" ;;
    *)                                              echo "unknown" ;;
  esac
}

usage() {
  cat <<EOF >&2
Usage: $0 [--check | --apply]
  --check   (default) report what would sync + Codex compatibility per skill
  --apply   copy the skills into \$CODEX_SKILLS_DIR (default ~/.agents/skills)
Env: CODEX_SKILLS_DIR overrides the destination.
EOF
}

MODE="${1:---check}"
case "$MODE" in
  --check|--apply) ;;
  -h|--help) usage; exit 0 ;;
  *) echo "unknown arg: $MODE" >&2; usage; exit 2 ;;
esac

echo "[$(date '+%Y-%m-%d %H:%M:%S')] sync-skills-to-codex.sh mode=$MODE dest=$DEST" >> "$LOG"
echo "[sync] src : $SRC_SKILLS"
echo "[sync] dest: $DEST"
echo ""

fail=0
for s in "${SKILLS[@]}"; do
  src="$SRC_SKILLS/$s"
  if [ ! -f "$src/SKILL.md" ]; then
    echo "  ✗ $s — source missing ($src/SKILL.md)"; fail=1; continue
  fi
  c="$(compat "$s")"
  if [ "$MODE" = "--check" ]; then
    echo "  • $s  →  $DEST/$s   [Codex: $c]"
  else
    mkdir -p "$DEST"
    rm -rf "${DEST:?}/$s"
    cp -R "$src" "$DEST/$s"
    echo "  ✓ $s synced  [Codex: $c]"
  fi
done

echo ""
if [ "$MODE" = "--check" ]; then
  echo "[sync] dry run only. Re-run with --apply to copy. Codex compatibility:"
  echo "       supported  = knowledge-manager-plain, knowledge-manager-lite"
  echo "       degraded   = knowledge-manager, knowledge-manager-bootstrap (AskUserQuestion)"
  echo "       UNSUPPORTED = knowledge-manager-at (Agent Teams = Claude Code only)"
else
  echo "[sync] done. Verify: start a Codex session / 'codex exec' and check the"
  echo "       active skill list includes the synced skills. Smoke-test"
  echo "       knowledge-manager-lite / -plain first (the supported ones)."
fi
exit $fail
