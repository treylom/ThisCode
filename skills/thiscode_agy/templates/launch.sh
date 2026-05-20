#!/bin/bash
# agy bridge launcher — Y-3 단발 + Y-2 PTY. 2-window pattern (mirror sshee/codex bridge layout).
# 단일 tmux 세션 $BOT_NAME 안에 2 windows: `agy` (agy CLI TUI, default focus) + `daemon` (bridge.py log).
# attach 하면 agy window 가 바로 보이고, C-b 0/1 로 window 전환.
set -euo pipefail

umask 077

# WD = bot project root (launch.sh's directory).
WD="$(cd "$(dirname "$0")" && pwd)"
cd "$WD"

BOT_NAME="${BOT_NAME:-mybot}"
CHANNEL_DIR="$HOME/.claude/channels/discord-$BOT_NAME"

# Wrapper 모드 — AGY_BRIDGE_ROLE 없으면 이전 세션 정리 + 신규 2-window 세션 생성 + attach.
# Note: no in-launch.sh suicide guard — if you wrap launch.sh in an outer "while true; do ./launch.sh; done"
# watchdog, an exit-0 guard would loop. Use your shell function to detect "called from inside session"
# and bootstrap from a separate context (see zshrc patterns).
if [[ -z "${AGY_BRIDGE_ROLE:-}" ]]; then
  if tmux has-session -t "$BOT_NAME" 2>/dev/null; then
    echo "[INFO] 이전 tmux 세션 '$BOT_NAME' 정리"
    tmux kill-session -t "$BOT_NAME"
  fi
  # .env 로드 (AGY_UNSAFE 등)
  source "$CHANNEL_DIR/.env" 2>/dev/null || true
  AGY_BIN_WRAPPER="${AGY_PATH:-$HOME/.local/bin/agy}"
  AGY_FLAG="--sandbox"
  [[ "${AGY_UNSAFE:-0}" == "1" ]] && AGY_FLAG="--dangerously-skip-permissions"

  echo "[INFO] tmux '$BOT_NAME' 생성 — 2 windows: 'agy' (TUI, default) + 'daemon' (bridge log)"
  # 1) 세션 생성 — agy window 가 0번 (default attach 시 첫 표시)
  tmux new -s "$BOT_NAME" -d -n agy "$AGY_BIN_WRAPPER $AGY_FLAG"
  sleep 0.3
  # 2) agy window target 확정 (AGY_TUI_PANE 으로 bridge.py 에 전달).
  # base-pane-index 환경 차이 흡수 위해 window 이름만 지정 (active pane 자동 선택).
  AGY_PANE_ID="${BOT_NAME}:agy"
  # 3) daemon window 추가 — bridge 시작
  tmux new-window -t "$BOT_NAME" -n daemon \
    "AGY_BRIDGE_ROLE=runner BOT_NAME='$BOT_NAME' AGY_TUI_PANE='$AGY_PANE_ID' exec bash '$0'"
  # 4) agy window 를 default focus 로
  tmux select-window -t "${BOT_NAME}:agy"
  echo "[INFO] agy TUI window = ${BOT_NAME}:agy · bridge daemon window = ${BOT_NAME}:daemon"
  echo "       attach: tmux attach -t $BOT_NAME (agy default; C-b 0/1 로 window 전환)"

  if [[ -n "${TMUX:-}" ]]; then
    exec tmux switch-client -t "$BOT_NAME"
  fi
  exec tmux attach -t "$BOT_NAME"
fi

# === runner mode (AGY_BRIDGE_ROLE=runner) — bridge daemon 실행 ===

if [[ ! -d .venv ]]; then
  echo "[FATAL] venv 미생성 — 'python3 -m venv .venv && .venv/bin/pip install -r requirements.txt' 먼저 실행"
  exit 1
fi
if [[ ! -f "$CHANNEL_DIR/.env" ]]; then
  echo "[FATAL] token .env 없음 — $CHANNEL_DIR/.env (DISCORD_BOT_TOKEN, AGY_PATH) 작성 필요"
  echo "  template: see thiscode_agy/templates/env.template in ThisCode skill"
  exit 1
fi

# AGY_PATH validation
AGY_PATH_VALIDATE="${AGY_PATH:-$HOME/.local/bin/agy}"
case "$AGY_PATH_VALIDATE" in
  /*) ;;
  *) echo "[FATAL] AGY_PATH must be absolute path, got: $AGY_PATH_VALIDATE"; exit 1 ;;
esac
if [[ ! -x "$AGY_PATH_VALIDATE" ]]; then
  echo "[FATAL] AGY_PATH not executable: $AGY_PATH_VALIDATE"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$CHANNEL_DIR/.env"
set +a
export DISCORD_STATE_DIR="$CHANNEL_DIR"

AGY_BIN="${AGY_PATH:-$HOME/.local/bin/agy}"
if [[ ! -x "$AGY_BIN" ]]; then
  echo "[FATAL] agy CLI 없음 ($AGY_BIN)"
  exit 1
fi

bash "$WD/scripts/setup_bot_dirs.sh" "$CHANNEL_DIR"

BRIDGE_LOG="$WD/state/logs/$(date +%Y-%m-%d)/bridge-launch.log"
mkdir -p "$(dirname "$BRIDGE_LOG")"
chmod 700 "$(dirname "$BRIDGE_LOG")"

echo "[INFO] BOT_NAME=$BOT_NAME"
echo "[INFO] AGY_TUI_PANE=$AGY_TUI_PANE (cross-window send-keys target)"
echo "[INFO] WD=$WD"
echo "[INFO] DISCORD_STATE_DIR=$DISCORD_STATE_DIR"
echo "[INFO] AGY_PATH=$AGY_BIN"
echo "[INFO] AGY_UNSAFE=${AGY_UNSAFE:-0}"
echo "[INFO] launch log=$BRIDGE_LOG"

cleanup() {
  echo "[INFO] bridge shutdown"
}
trap cleanup EXIT INT TERM

exec "$WD/.venv/bin/python3" -u "$WD/scripts/bridge.py" 2>&1 | tee -a "$BRIDGE_LOG"
