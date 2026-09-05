#!/usr/bin/env bash
# install-obsidian-cli.sh — Obsidian CLI / app detect + install (Tier 2 fallback).
# v2.3: v2.1.1 backbone + 출처 명시.
# 출처: obsidian.md (proprietary GUI, 별도 download 필요)
# CLI 후보 (3-binary detect): obsidian-cli / obsidian / notesmd-cli
# 본 script 는 GUI 자체 vendor 불가 (proprietary) — install_obsidian() 안 brew cask / WSL Windows guide / Linux .deb 안내.
set -euo pipefail

OS="$(uname -s)"
WSL=0
[ -f /proc/version ] && grep -qi microsoft /proc/version && WSL=1

usage() {
  cat <<EOF >&2
Usage: $0 [--check] [--json] [--apply]
  (no arg)     detect → 미설치 시 interactive prompt 로 install 시도
  --check      detect 결과 stdout (exit 0 = present / 1 = missing)
  --check --json   wizard 호환 JSON 출력 (obsidian_cli / obsidian_app / os)
  --apply      prompt 없이 install 강제 (macOS brew cask / WSL 안내 / Linux 안내)
EOF
}

CHECK_ONLY=0
JSON_OUT=0
APPLY=0

for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --json) JSON_OUT=1 ;;
    --apply) APPLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; usage; exit 2 ;;
  esac
done

# Detect CLI binary (3 candidates — v2.0.2 fix)
detect_cli() {
  for c in obsidian-cli obsidian notesmd-cli; do
    if command -v "$c" >/dev/null 2>&1; then
      command -v "$c"
      return 0
    fi
  done
  return 1
}

# Detect Obsidian app (Mac / WSL / Linux)
detect_app() {
  case "$OS" in
    Darwin)
      [ -d "/Applications/Obsidian.app" ] && { echo "/Applications/Obsidian.app"; return 0; }
      ;;
    Linux)
      if [ "$WSL" = "1" ] && [ -f "/mnt/c/Program Files/Obsidian/Obsidian.exe" ]; then
        echo "/mnt/c/Program Files/Obsidian"; return 0
      fi
      [ -x "$HOME/.local/bin/obsidian" ] && { echo "$HOME/.local/bin/obsidian"; return 0; }
      ;;
  esac
  return 1
}

# --check --json (wizard 호환)
if [ "$JSON_OUT" = "1" ] && [ "$CHECK_ONLY" = "1" ]; then
  local_cli="$(detect_cli || true)"
  local_app="$(detect_app || true)"
  jq -n \
    --arg cli "$local_cli" \
    --arg app "$local_app" \
    --arg os "$OS" \
    '{ obsidian_cli: $cli, obsidian_app: $app, os: $os }'
  exit 0
fi

# --check (no --json)
if [ "$CHECK_ONLY" = "1" ]; then
  if cli_path="$(detect_cli)"; then
    echo "obsidian-cli: present ($cli_path)"
    exit 0
  elif app_path="$(detect_app)"; then
    echo "obsidian app: present ($app_path) — CLI missing"
    exit 0
  else
    echo "obsidian: missing — fallback to Tier 4 (ripgrep)"
    exit 1
  fi
fi

# install_obsidian (no-arg interactive 또는 --apply)
install_obsidian() {
  case "$OS" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        echo "[install] brew install --cask obsidian"
        brew install --cask obsidian
      else
        echo "[install] brew not found — manual: https://obsidian.md/download" >&2
        return 1
      fi
      ;;
    Linux)
      if [ "$WSL" = "1" ]; then
        echo "[install] WSL detected — install Obsidian on Windows side:" >&2
        echo "  https://obsidian.md/download" >&2
        echo "  Tier 2 (CLI) skip → Tier 3 (MCP) → Tier 4 (ripgrep) fallback" >&2
        return 1
      fi
      if command -v apt-get >/dev/null 2>&1; then
        echo "[install] Linux .deb 수동 download 필요:" >&2
        echo "  https://obsidian.md/download" >&2
        return 1
      fi
      echo "[install] unknown package manager — manual install" >&2
      return 1
      ;;
    *)
      echo "[install] unsupported OS: $OS" >&2
      return 1
      ;;
  esac
}

# detect + interactive prompt 또는 --apply
if cli_path="$(detect_cli)"; then
  echo "obsidian-cli: present ($cli_path) — install skip"
  exit 0
fi

echo "obsidian-cli: missing"
if [ "$APPLY" = "1" ]; then
  install_obsidian
  exit $?
fi

# no-arg interactive
read -r -p "Obsidian CLI 미설치. install 시도할까요? [y/N] " ANS
[ "${ANS:-N}" = "y" ] || [ "${ANS:-N}" = "Y" ] && install_obsidian || {
  echo "[install] skip — Tier 4 (ripgrep) 가 fallback"
  exit 0
}
