#!/usr/bin/env bash
# install-graphrag.sh — thiscode v2.3
# GraphRAG FastAPI server (port 8400) — Tier 1 search 백엔드
# v2.3: v2.1.1 backbone + vault SoT 의존 → thiscode vendor/graphrag/ 의존 정정
#       venv 위치 = ~/.cache/thiscode/graphrag/venv (writable home cache)
# 출처: thiscode/vendor/graphrag/ ← obsidian-ai-vault `.team-os/graphrag/` vendor 박제
# RRF 가중치: α=0.3 (Dense) / β=0.4 (Sparse) / γ=0.15 (Decomposed) / δ=0.15 (Entity)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DISCODE_HOME="${CLAUDE_DISCODE_HOME:-$(cd "$SCRIPT_DIR/.." && pwd)}"
GRAPHRAG_VENDOR="$CLAUDE_DISCODE_HOME/vendor/graphrag"
GRAPHRAG_VENV="${HOME}/.cache/thiscode/graphrag/venv"
GRAPHRAG_RUN="${HOME}/.cache/thiscode/graphrag/run"
ENTRY_MODULE="search_server:app"
PORT=8400

usage() {
  cat <<EOF >&2
Usage: $0 [--check | --apply | --preflight]
  --check      (default) health probe + venv/requirements report
  --apply      preflight → venv → pip install → uvicorn nohup
  --preflight  preflight only (Python / disk / port / vendor SoT)
EOF
}

MODE=check
case "${1:-}" in
  --check)     MODE=check ;;
  --apply)     MODE=apply ;;
  --preflight) MODE=preflight ;;
  -h|--help)   usage; exit 0 ;;
  "")          MODE=check ;;
  *)           echo "unknown arg: $1" >&2; usage; exit 2 ;;
esac

preflight() {
  local fail=0
  echo "[preflight] Python 3.10+ check..."
  # v2.3.2: regex 안 3.9 false pass 정정 — sys.version_info tuple compare 사용
  if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    echo "  ✗ Python 3.10+ 필요 (vendored code uses 3.10 syntax: Path | str)" >&2; fail=1
  else
    echo "  ✓ $(python3 --version 2>&1)"
  fi
  echo "[preflight] disk 5GB+ check..."
  local free_kb free_gb
  free_kb=$(df -k "$HOME" 2>/dev/null | tail -n 1 | awk '{print $4}')
  free_gb=$(( ${free_kb:-0} / 1024 / 1024 ))
  if [ "$free_gb" -lt 5 ]; then
    echo "  ✗ disk 5GB+ 필요 (현재 ${free_gb}GB)" >&2; fail=1
  else
    echo "  ✓ ${free_gb}GB free"
  fi
  echo "[preflight] RAM check (GraphRAG Tier 1 = memory-heavy)..."
  local ram_gb=0
  if [ "$(uname)" = "Darwin" ]; then
    ram_gb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1024 / 1024 / 1024 ))
  else
    ram_gb=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0) / 1024 / 1024 ))
  fi
  if [ "${ram_gb:-0}" -lt 8 ]; then
    echo "  ⚠ RAM ${ram_gb}GB < 8GB 권장. GraphRAG(Dense embedding + FastAPI + index)는 메모리 과다 — 저사양에서 thrash 위험." >&2
    echo "    → 권고: GraphRAG 미사용, Obsidian CLI(Tier 2) 사용: bash scripts/install-obsidian-cli.sh (로컬 전문 검색으로 시작)" >&2
    echo "    → 그래도 설치 강행: GRAPHRAG_FORCE=1 $0 --apply" >&2
    if [ "$MODE" = "apply" ] && [ "${GRAPHRAG_FORCE:-0}" != "1" ]; then
      echo "  ✗ RAM 부족 — apply 중단 (Obsidian CLI 권고. override: GRAPHRAG_FORCE=1)" >&2; fail=1
    fi
  else
    echo "  ✓ RAM ${ram_gb}GB"
  fi
  echo "[preflight] port $PORT check..."
  if nc -z localhost "$PORT" 2>/dev/null; then
    echo "  ⚠ port $PORT in use (may be existing GraphRAG — apply will skip start)" >&2
  else
    echo "  ✓ port $PORT free"
  fi
  echo "[preflight] vendor SoT check..."
  if [ ! -d "$GRAPHRAG_VENDOR/scripts" ]; then
    echo "  ✗ vendor/graphrag/scripts/ missing at $GRAPHRAG_VENDOR" >&2; fail=1
  else
    local n
    n=$(find "$GRAPHRAG_VENDOR/scripts" -maxdepth 1 -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
    echo "  ✓ vendor SoT present ($n Python files)"
  fi
  return $fail
}

if [ "$MODE" = "preflight" ]; then
  preflight
  exit $?
fi

if [ "$MODE" = "check" ]; then
  local_fail=0
  echo "python3: $(command -v python3 2>/dev/null || { echo MISSING; local_fail=1; })"
  if [ -d "$GRAPHRAG_VENDOR/scripts" ]; then
    echo "vendor SoT: $GRAPHRAG_VENDOR/scripts present"
  else
    echo "vendor SoT: $GRAPHRAG_VENDOR/scripts MISSING (required — vendor 박제 누락)"
    local_fail=1
  fi
  if [ -f "$GRAPHRAG_VENDOR/scripts/requirements.txt" ]; then
    echo "requirements: $GRAPHRAG_VENDOR/scripts/requirements.txt present"
  else
    echo "requirements: $GRAPHRAG_VENDOR/scripts/requirements.txt MISSING (required)"
    local_fail=1
  fi
  echo "venv: $GRAPHRAG_VENV $([ -d "$GRAPHRAG_VENV" ] && echo present || echo 'not yet (run --apply)')"
  if curl -s --connect-timeout 1 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q ok; then
    echo "GraphRAG server: running on port $PORT"
  else
    echo "GraphRAG server: not running (optional — Tier 1 fall through)"
  fi
  if [ "$local_fail" -eq 0 ]; then
    exit 0
  else
    echo "[--check] required artifact MISSING — run --apply to fix" >&2
    exit 5
  fi
fi

# MODE=apply
if ! command -v python3 >/dev/null; then
  echo "python3 missing — install python3 first" >&2
  exit 4
fi

preflight || { echo "[apply] preflight FAILED — fix issues above" >&2; exit 1; }

if [ ! -d "$GRAPHRAG_VENDOR/scripts" ]; then
  echo "vendor/graphrag/scripts/ missing — thiscode repo corrupted?" >&2
  echo "  Expected: $GRAPHRAG_VENDOR/scripts/ (vendored from vault SoT)" >&2
  exit 5
fi

mkdir -p "$GRAPHRAG_RUN"

# v2.3.2: flock — concurrent --apply 안 race condition 차단 (codex Axis B CRITICAL)
LOCK="$GRAPHRAG_RUN/install.lock"
PIDFILE="$GRAPHRAG_RUN/graphrag.pid"
exec 9>"$LOCK"
if command -v flock >/dev/null 2>&1; then
  flock -n 9 || { echo "[apply] another GraphRAG install is running (flock $LOCK)" >&2; exit 7; }
fi

# v2.3.2.2: venv in-place create (atomic rename 제거 — broken venv 차단)
# venv internal pyvenv.cfg + symlinks 안 absolute path hardcoded → mv 후 broken.
# corrupt venv 안 idempotency = rm -rf + 재create.
if [ ! -x "$GRAPHRAG_VENV/bin/python" ] || [ ! -x "$GRAPHRAG_VENV/bin/pip" ]; then
  echo "[apply] (re)creating venv at $GRAPHRAG_VENV (in-place)..."
  rm -rf "$GRAPHRAG_VENV"
  python3 -m venv "$GRAPHRAG_VENV"
fi
echo "[apply] pip install requirements (verbose for debug)..."
# v2.3.2.1: --quiet 제거 — silent fail 차단 (CI 안 networkx import fail mystery 검증)
"$GRAPHRAG_VENV/bin/python" -m pip install --upgrade pip
"$GRAPHRAG_VENV/bin/python" -m pip install --retries 3 --timeout 60 -r "$GRAPHRAG_VENDOR/scripts/requirements.txt"
echo "[apply] pip install complete — verifying installed packages..."
"$GRAPHRAG_VENV/bin/python" -m pip list 2>&1 | grep -iE "networkx|community|louvain|fastapi|uvicorn|numpy|httpx|pyyaml" || true

# v2.3.2: post-lock health probe (concurrent install 안 두 번째 안 already healthy)
if curl -fsS --connect-timeout 1 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q ok; then
  echo "[apply] GraphRAG server already healthy on port $PORT — skip start"
  exit 0
fi

# v2.3.2: port occupied but non-GraphRAG = explicit fail (안 안전 mask)
if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 "$PORT" 2>/dev/null; then
  echo "[apply] port $PORT is occupied but /health is not GraphRAG" >&2
  echo "  Manual: 본 port 사용 process 확인 + cleanup 의무" >&2
  exit 7
fi

# v2.3.2: cleanup trap — failed health 시 orphan uvicorn 방지
STARTED_PID=""
cleanup() {
  if [ -n "$STARTED_PID" ] && kill -0 "$STARTED_PID" 2>/dev/null; then
    kill "$STARTED_PID" 2>/dev/null || true
    sleep 1
    kill -9 "$STARTED_PID" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

echo "[apply] starting GraphRAG server (uvicorn, background)..."
nohup "$GRAPHRAG_VENV/bin/python" -m uvicorn --app-dir "$GRAPHRAG_VENDOR/scripts" "$ENTRY_MODULE" \
  --host 127.0.0.1 --port "$PORT" >"$GRAPHRAG_RUN/graphrag.log" 2>&1 &
STARTED_PID=$!
PID=$STARTED_PID
echo "[apply] pid=$PID — waiting for health (10s)..."

for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1
  if curl -fsS --connect-timeout 1 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q ok; then
    echo "[apply] ✓ GraphRAG server running on port $PORT (pid=$PID)"
    echo "$PID" > "$PIDFILE"
    trap - INT TERM EXIT
    exit 0
  fi
done

echo "[apply] ⚠ server not responding after 10s — check $GRAPHRAG_RUN/graphrag.log" >&2
echo "[apply] last 5 lines of graphrag.log:" >&2
tail -n 5 "$GRAPHRAG_RUN/graphrag.log" 2>/dev/null >&2 || true
# cleanup trap 안 spawned uvicorn kill (orphan 차단)
exit 6
