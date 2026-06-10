#!/usr/bin/env bash
# thiscode healthcheck — v2.3 Phase progress + v1.0.0 exit code / log / redact 보강
# Exit codes: 0 = all required OK / 1 = required FAIL / 2 = intentional NOT YET only
set -euo pipefail

LOG="${HOME}/.thiscode-setup.log"

# Redact user-specific paths in log entries (v1.0.0 Round 2 outcome)
redact() {
  echo "$1" | sed -E "s|$HOME|/HOME|g; s|/Users/[^/]+|/Users/REDACTED|g; s|/home/[^/]+|/home/REDACTED|g"
}

# Color output (TTY only)
if [ -t 1 ]; then
  green() { printf "\033[32m✓\033[0m"; }
  red()   { printf "\033[31m✗\033[0m"; }
  gray()  { printf "\033[90m○\033[0m"; }
else
  green() { printf "✓"; }
  red()   { printf "✗"; }
  gray()  { printf "○"; }
fi

echo "[$(date)] healthcheck start" >> "$LOG"

ok=0
fail=0
skip=0

phase_check() {
  local phase="$1" name="$2" cmd="$3" required="$4"
  if eval "$cmd" >/dev/null 2>&1; then
    printf "%s %-40s : OK\n" "$(green)" "$phase $name"
    ok=$((ok + 1))
  elif [ "$required" = "required" ]; then
    printf "%s %-40s : FAIL\n" "$(red)" "$phase $name"
    echo "[$(date)] FAIL $phase $name ($(redact "$cmd"))" >> "$LOG"
    fail=$((fail + 1))
  else
    printf "%s %-40s : NOT YET\n" "$(gray)" "$phase $name"
    skip=$((skip + 1))
  fi
}

echo "thiscode healthcheck v2.3 — Phase progress"
echo "─────────────────────────────────"

phase_check "Phase 0" "superpowers (plugin)"          "claude plugin list 2>/dev/null | grep -qi superpowers" "optional"
phase_check "Phase 1" "ripgrep (Tier 4)"              "command -v rg || command -v grep" "required"
phase_check "Phase 2" "obsidian-cli (Tier 3)"         "command -v obsidian-cli || command -v obsidian || command -v notesmd-cli" "optional"
phase_check "Phase 3" "vault-search MCP (Tier 2)"     "claude mcp get vault-search 2>/dev/null || jq -e '.mcpServers.\"vault-search\"' ${HOME}/.config/claude/claude_desktop_config.json 2>/dev/null" "optional"
phase_check "Phase 4" "GraphRAG (Tier 1)"             "curl -fsS http://localhost:8400/health 2>/dev/null" "optional"
phase_check "Phase 5" "Dense embedding (4-channel)"   "${HOME}/.cache/thiscode/graphrag/venv/bin/python -c 'import torch, transformers, sentence_transformers' 2>/dev/null" "optional"

echo "─────────────────────────────────"
if [ "$fail" -eq 0 ]; then
  printf "Summary: %d OK, %d NOT YET (all required passed) ✅\n" "$ok" "$skip"
  echo "[$(date)] healthcheck PASS (ok=$ok skip=$skip)" >> "$LOG"
  if [ "$skip" -gt 0 ]; then
    exit 2
  else
    exit 0
  fi
else
  printf "Summary: %d OK, %d FAIL, %d NOT YET ❌\n" "$ok" "$fail" "$skip"
  echo "see log: $LOG"
  echo "[$(date)] healthcheck FAIL (ok=$ok fail=$fail skip=$skip)" >> "$LOG"
  exit 1
fi
