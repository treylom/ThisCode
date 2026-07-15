#!/usr/bin/env bash
set -euo pipefail

INPUT_JSON="/tmp/graphrag_judge_input.json"
JUDGE_JSON="/tmp/graphrag_llm_judges.json"
SCORE_JSON="/tmp/graphrag_full_llm_score.json"

if [[ ! -f "$INPUT_JSON" ]]; then
  echo "ERROR: Missing benchmark input: $INPUT_JSON" >&2
  exit 1
fi

python3 .team-os/graphrag/scripts/benchmark_judge.py --help 2>&1 | grep -q "\-\-mode" || {
  echo "ERROR: --mode flag not yet available. Wait for llm-judge-dev to complete." >&2
  exit 1
}

python3 .team-os/graphrag/scripts/benchmark_judge.py "$INPUT_JSON" --mode llm --output "$JUDGE_JSON"
python3 .team-os/graphrag/scripts/benchmark_scorer.py "$INPUT_JSON" --judges "$JUDGE_JSON" --output "$SCORE_JSON"
python3 -c "import json; d=json.load(open('$SCORE_JSON')); print(d['composite']['composite'])"
