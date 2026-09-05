#!/usr/bin/env bash
# install-superpowers.sh — thiscode v2.3
# Anthropic 공식 superpowers plugin install via Claude Code plugin manager.
# 출처: github.com/anthropics/claude-plugins-official/superpowers (MIT)
# 본 script 는 plugin manager 호출 wrapper — plugin marketplace 가용성 의존.
set -euo pipefail

MODE="${1:---apply}"
LOG="${HOME}/.thiscode-setup.log"

usage() {
  cat <<EOF >&2
Usage: $0 [--check | --apply]
  --check      plugin install 여부만 확인 (exit 0 = present / 1 = missing)
  --apply      (default) plugin install 실행
EOF
}

case "$MODE" in
  --check)
    if claude plugin list 2>/dev/null | grep -qi "superpowers"; then
      echo "✓ superpowers plugin installed"
      exit 0
    else
      echo "✗ superpowers plugin missing"
      exit 1
    fi
    ;;
  --apply)
    if ! command -v claude >/dev/null 2>&1; then
      echo "✗ Claude Code CLI not found." >&2
      echo "  Install: https://claude.ai/code" >&2
      exit 1
    fi
    if claude plugin list 2>/dev/null | grep -qi "superpowers"; then
      echo "✓ superpowers already installed — skip"
      exit 0
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] install-superpowers.sh mode=$MODE" >> "$LOG"
    echo "[apply] Installing superpowers plugin via Claude Code plugin manager..."
    if claude plugin install superpowers@claude-plugins-official 2>>"$LOG"; then
      echo "✓ superpowers installed"
      exit 0
    else
      echo "✗ plugin install failed." >&2
      echo "  Likely cause: marketplace not registered. Try:" >&2
      echo "    claude plugin marketplace update claude-plugins-official" >&2
      echo "    # or" >&2
      echo "    claude plugin marketplace add anthropics/claude-plugins-official" >&2
      echo "  Then retry: claude plugin install superpowers@claude-plugins-official" >&2
      echo "  See: ATTRIBUTIONS.md (superpowers entry)" >&2
      exit 2
    fi
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    echo "unknown arg: $MODE" >&2
    usage
    exit 2
    ;;
esac
