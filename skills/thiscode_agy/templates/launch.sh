#!/bin/bash
# agy bridge launcher — Y-3 단발 + Y-2 PTY.
# Codex bridge launch.sh pattern mirror. 다만 logs 는 /tmp 대신 $WD/state/logs (mode 700).
# 2026-05-20 재경님 지시: 이전 세션 자동 정리 + self-rerun pattern (tmux 밖에서 호출 시 wrapper 모드).
set -euo pipefail

umask 077

# WD = bot project root (launch.sh's directory).
# Templates ship launch.sh at project root; .py files live in $WD/scripts/.
WD="$(cd "$(dirname "$0")" && pwd)"
cd "$WD"

# Bot 정체성 — alias 와 일치하는 단일 토큰 (BOT_NAME env 로 override). tmux 세션 + ~/.claude/channels/discord-<name>/ 이름.
BOT_NAME="${BOT_NAME:-mybot}"
CHANNEL_DIR="$HOME/.claude/channels/discord-$BOT_NAME"

# Wrapper 모드 — AGY_BRIDGE_ROLE 없으면 이전 세션 정리 + tmux 세션 (위=bridge daemon, 아래=agy CLI 인터랙티브) + attach.
# 두 번째 pane 에 agy CLI 직접 띄움 (Discord bridge daemon 과 별도, 사용자 직접 prompt 가능).
# nested tmux 케이스 (Claude Code 가 tmux 안 실행) cover — TMUX 변수 아닌 별도 marker 사용.
if [[ -z "${AGY_BRIDGE_ROLE:-}" ]]; then
  # Suicide guard — 이미 같은 이름 tmux session 안에서 wrapper 호출 시 자기 자신 kill 차단.
  # 사용자가 attached 상태에서 alias 재실행할 때 발생 (이전 회귀 사례 반영).
  if [[ -n "${TMUX:-}" ]] && tmux display-message -p "#S" 2>/dev/null | grep -qx "$BOT_NAME"; then
    echo "[WARN] 이미 '$BOT_NAME' tmux 세션 안 — wrapper 자살 가드 (kill+restart 거부)"
    echo "       강제 재시작은 detach (Ctrl+B,D) 후 다른 터미널에서 alias 재실행"
    exit 0
  fi
  if tmux has-session -t "$BOT_NAME" 2>/dev/null; then
    echo "[INFO] 이전 tmux 세션 '$BOT_NAME' 정리"
    tmux kill-session -t "$BOT_NAME"
  fi
  # AGY 인터랙티브 flag — .env 의 AGY_UNSAFE 따라
  source "$HOME/.claude/channels/discord-$BOT_NAME/.env" 2>/dev/null || true
  AGY_BIN_WRAPPER="${AGY_PATH:-$HOME/.local/bin/agy}"
  AGY_FLAG="--sandbox"
  [[ "${AGY_UNSAFE:-0}" == "1" ]] && AGY_FLAG="--dangerously-skip-permissions"
  echo "[INFO] tmux '$BOT_NAME' 생성 — 2-step: placeholder → split → env 확정 후 bridge 시작 · 아래=agy CLI 인터랙티브 (default focus)"
  # 2-step launch — base-pane-index 무관하게 정확한 pane id 결정한 다음 bridge.py 가동.
  # 1) 빈 placeholder bash pane 으로 세션 생성
  tmux new -s "$BOT_NAME" -d "bash"
  sleep 0.3
  # 2) split-window 로 agy pane 생성 → pane id 캡처 (-P -F)
  AGY_PANE_ID="$(tmux split-window -t "$BOT_NAME" -v -p 60 -P -F '#{session_name}:#{window_index}.#{pane_index}' "$AGY_BIN_WRAPPER $AGY_FLAG")"
  # 3) daemon pane id = 첫 pane (split 전 placeholder)
  DAEMON_PANE_INDEX="$(tmux list-panes -t "$BOT_NAME" -F '#{pane_index}' | head -1)"
  DAEMON_PANE="${BOT_NAME}:$(tmux list-windows -t "$BOT_NAME" -F '#{window_index}' | head -1).${DAEMON_PANE_INDEX}"
  echo "[INFO] agy TUI pane = $AGY_PANE_ID · bridge daemon pane = $DAEMON_PANE"
  # 4) daemon pane 에 bridge runner 명령 send-keys (정확한 AGY_TUI_PANE env 포함)
  tmux send-keys -t "$DAEMON_PANE" "AGY_BRIDGE_ROLE=runner BOT_NAME='$BOT_NAME' AGY_TUI_PANE='$AGY_PANE_ID' exec bash '$0'" Enter
  tmux select-pane -t "$AGY_PANE_ID" 2>/dev/null || true
  if [[ -n "${TMUX:-}" ]]; then
    exec tmux switch-client -t "$BOT_NAME"
  fi
  exec tmux attach -t "$BOT_NAME"
fi

# 사전 점검
if [[ ! -d .venv ]]; then
  echo "[FATAL] venv 미생성 — 'python3 -m venv .venv && .venv/bin/pip install -r requirements.txt' 먼저 실행"
  exit 1
fi
if [[ ! -f "$CHANNEL_DIR/.env" ]]; then
  echo "[FATAL] token .env 없음 — $CHANNEL_DIR/.env (DISCORD_BOT_TOKEN, AGY_PATH) 작성 필요"
  echo "  template: see thiscode_agy/templates/env.template in ThisCode skill"
  exit 1
fi

# AGY_PATH validation — absolute executable path 만 허용 (.env 가 shell-sourced 되므로 untrusted content 방지 차원).
AGY_PATH_VALIDATE="${AGY_PATH:-$HOME/.local/bin/agy}"
case "$AGY_PATH_VALIDATE" in
  /*) ;;  # absolute, OK
  *) echo "[FATAL] AGY_PATH must be absolute path, got: $AGY_PATH_VALIDATE"; exit 1 ;;
esac
if [[ ! -x "$AGY_PATH_VALIDATE" ]]; then
  echo "[FATAL] AGY_PATH not executable: $AGY_PATH_VALIDATE"
  exit 1
fi

# .env load
set -a
# shellcheck disable=SC1091
source "$CHANNEL_DIR/.env"
set +a
export DISCORD_STATE_DIR="$CHANNEL_DIR"

# agy CLI 존재 검증
AGY_BIN="${AGY_PATH:-$HOME/.local/bin/agy}"
if [[ ! -x "$AGY_BIN" ]]; then
  echo "[FATAL] agy CLI 없음 ($AGY_BIN)"
  exit 1
fi

# 디렉토리 셋업 (idempotent)
bash "$WD/scripts/setup_bot_dirs.sh" "$CHANNEL_DIR"

BRIDGE_LOG="$WD/state/logs/$(date +%Y-%m-%d)/bridge-launch.log"
mkdir -p "$(dirname "$BRIDGE_LOG")"
chmod 700 "$(dirname "$BRIDGE_LOG")"

echo "[INFO] BOT_NAME=$BOT_NAME"
echo "[INFO] WD=$WD"
echo "[INFO] DISCORD_STATE_DIR=$DISCORD_STATE_DIR"
echo "[INFO] AGY_PATH=$AGY_BIN"
echo "[INFO] AGY_UNSAFE=${AGY_UNSAFE:-0}"
echo "[INFO] launch log=$BRIDGE_LOG"

# cleanup trap
cleanup() {
  echo "[INFO] bridge shutdown"
}
trap cleanup EXIT INT TERM

# bridge daemon (foreground)
exec "$WD/.venv/bin/python3" -u "$WD/scripts/bridge.py" 2>&1 | tee -a "$BRIDGE_LOG"
