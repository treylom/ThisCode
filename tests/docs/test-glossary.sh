#!/usr/bin/env bash
set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
F="$REPO_ROOT/docs/GLOSSARY.md"
test -f "$F" || { echo "FAIL: GLOSSARY.md not found"; exit 1; }
TERMS=$(grep -E "^### " "$F" | wc -l)
[ "$TERMS" -ge 30 ] || { echo "FAIL: expected 30+ terms, got $TERMS"; exit 1; }
for t in "LLM" "MCP" "CEL" "embedding" "recall" "kg_depth" "Tier" "fallback" "RAG"; do
  grep -q "^### $t" "$F" || { echo "FAIL: missing term $t"; exit 1; }
done
echo "PASS GLOSSARY ($TERMS terms)"
