#!/usr/bin/env bash
# install-ripgrep.sh — thiscode v2.3
# ripgrep install — multi package manager (brew / apt / dnf / apk).
# 출처: github.com/BurntSushi/ripgrep (Unlicense + MIT dual)
# Windows native = scoop install ripgrep (사용자 manual, 본 script 안 미지원).
set -euo pipefail

MODE="${1:---apply}"
LOG="${HOME}/.thiscode-setup.log"

usage() {
  cat <<EOF >&2
Usage: $0 [--check | --apply]
  --check      ripgrep 설치 여부만 확인 (exit 0 = present / 1 = missing)
  --apply      (default) OS detect + 패키지 매니저 install
EOF
}

case "$MODE" in
  -h|--help) usage; exit 0 ;;
  --check|--apply) ;;
  *) echo "unknown arg: $MODE" >&2; usage; exit 2 ;;
esac

if command -v rg >/dev/null 2>&1; then
  echo "✓ ripgrep already installed ($(rg --version 2>/dev/null | head -1))"
  exit 0
fi

case "$MODE" in
  --check)
    echo "✗ ripgrep missing"
    exit 1
    ;;
  --apply)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] install-ripgrep.sh mode=$MODE" >> "$LOG"
    OS="$(uname -s)"
    case "$OS" in
      Darwin)
        if command -v brew >/dev/null 2>&1; then
          echo "[apply] brew install ripgrep..."
          brew install ripgrep 2>>"$LOG"
        else
          echo "✗ Homebrew not found." >&2
          echo "  Install: https://brew.sh" >&2
          echo "  또는 manual: https://github.com/BurntSushi/ripgrep#installation" >&2
          exit 1
        fi
        ;;
      Linux)
        if command -v apt-get >/dev/null 2>&1; then
          echo "[apply] apt-get update + install ripgrep..."
          # v2.3.2: stale index 차단 (codex Axis B IMPORTANT)
          sudo apt-get update -y 2>>"$LOG"
          sudo apt-get install -y ripgrep 2>>"$LOG"
        elif command -v dnf >/dev/null 2>&1; then
          echo "[apply] dnf install ripgrep..."
          sudo dnf install -y ripgrep 2>>"$LOG"
        elif command -v apk >/dev/null 2>&1; then
          echo "[apply] apk add ripgrep..."
          sudo apk add ripgrep 2>>"$LOG"
        else
          echo "✗ No supported package manager (apt / dnf / apk)." >&2
          echo "  Manual install: https://github.com/BurntSushi/ripgrep#installation" >&2
          exit 1
        fi
        ;;
      *)
        echo "✗ Unsupported OS: $OS" >&2
        echo "  Windows native = scoop install ripgrep (사용자 직접 install)" >&2
        echo "  WSL 2 환경에서는 Linux 분기 자동 작동" >&2
        exit 1
        ;;
    esac
    if command -v rg >/dev/null 2>&1; then
      echo "✓ ripgrep installed ($(rg --version 2>/dev/null | head -1))"
      exit 0
    else
      echo "✗ install verification failed" >&2
      exit 2
    fi
    ;;
esac
