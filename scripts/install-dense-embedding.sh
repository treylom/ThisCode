#!/usr/bin/env bash
# install-dense-embedding.sh — thiscode v2.3
# Dense channel (4-channel RRF) — torch + transformers + sentence-transformers
# 출처:
#   PyTorch: github.com/pytorch/pytorch (BSD-3)
#   transformers: github.com/huggingface/transformers (Apache 2.0)
#   sentence-transformers: github.com/UKPLab/sentence-transformers (Apache 2.0)
# 본 dep ~1GB install footprint — 사용자 confirm 1회 (--apply mode).
# 미설치 시 = 3-channel fallback (Sparse + Decomposed + Entity).
set -euo pipefail

MODE="${1:---apply}"
LOG="${HOME}/.thiscode-setup.log"
VENV="${CLAUDE_DISCODE_VENV:-${HOME}/.cache/thiscode/graphrag/venv}"

usage() {
  cat <<EOF >&2
Usage: $0 [--check | --apply | --yes]
  --check      Dense deps import 여부만 확인 (exit 0 / 1)
  --apply      (default) 사용자 confirm 1회 + pip install
  --yes        confirm skip + 즉시 install (CI 용)
EOF
}

case "$MODE" in
  --check)
    if [[ -f "$VENV/bin/python" ]] && "$VENV/bin/python" -c "import torch, transformers, sentence_transformers" 2>/dev/null; then
      echo "✓ Dense embedding deps installed"
      exit 0
    else
      echo "✗ Dense embedding deps missing (3-channel mode OK)"
      exit 1
    fi
    ;;
  --apply|--yes)
    if [[ ! -d "$VENV" ]]; then
      echo "✗ GraphRAG venv not found at $VENV." >&2
      echo "  install-graphrag.sh --apply 먼저 실행 의무" >&2
      exit 1
    fi
    if "$VENV/bin/python" -c "import torch, transformers, sentence_transformers" 2>/dev/null; then
      echo "✓ Dense embedding deps already installed — skip"
      exit 0
    fi
    if [[ "$MODE" == "--apply" ]]; then
      cat <<'EOF'

⚠️  Dense embedding channel 활성화 옵션
   - Dense 4-channel RRF (Dense + Sparse + Decomposed + Entity) 작동
   - install footprint: ~1GB (PyTorch wheel + transformers + HF model cache)
   - 시간: 3–5 분
   - 미설치 시: 3-channel 모드 자동 fallback (Sparse + Decomposed + Entity)
EOF
      read -r -p "진행? [y/N] " ans
      case "${ans:-N}" in
        y|Y|yes|YES) ;;
        *)
          echo "○ Dense skip — 3-channel 모드 fallback"
          exit 0
          ;;
      esac
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] install-dense-embedding.sh mode=$MODE" >> "$LOG"
    echo "[apply] pip install torch + transformers + sentence-transformers..."
    "$VENV/bin/pip" install --progress-bar=on torch transformers sentence-transformers 2>>"$LOG"
    if "$VENV/bin/python" -c "import torch, transformers, sentence_transformers" 2>/dev/null; then
      echo "✓ Dense embedding installed"
      exit 0
    else
      echo "✗ install verification failed" >&2
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
