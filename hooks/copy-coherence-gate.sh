#!/bin/bash
# copy-coherence-gate.sh — routing gate for fact-document copies (fail-open)
#
# When a "fact document" (rules, skills, playbooks, soul/CLAUDE/AGENTS files) is
# edited or committed, inject a one-shot instruction telling the agent to sweep
# for living copies of the same fact in other files. It never blocks — it routes.
#
# Dual anchor (recommended registration = USER-GLOBAL ~/.claude/settings.json;
# see docs/rules-system.md "Hook scope" for why a project-root registration can
# miss nested bot WDs — installs that register at project root work when every
# session WD sits under that root, but the user-global path is the safe default):
#   PostToolUse  Write|Edit|MultiEdit  ->  copy-coherence-gate.sh post-edit
#   PreToolUse   Bash                  ->  copy-coherence-gate.sh pre-commit
# The two anchors overlap zero: post-edit sees tool edits, pre-commit sees the
# staged set (including files edited outside Write/Edit, e.g. via bash).
#
# Delivery lesson (measured 2026-08-05, per surface): plain hook stdout is NOT
# injected into the model context (measured on UserPromptSubmit — headless probe
# returned NONE); the JSON hookSpecificOutput.additionalContext path IS delivered
# on PostToolUse (measured: positive probe on a fact-doc Write saw the guidance,
# negative probe on a non-target Write did not). Emit the JSON envelope —
# "the hook fired" and "the agent received it" are two different measurements.

set -uo pipefail
MODE="${1:-post-edit}"
INPUT=$(cat 2>/dev/null || true)

# Fact-document predicate. Excluded: dated single-ledger files (YYYY-MM-DD-*),
# meeting ledgers, per-bot memory (basename-only anchors measured 64% false
# positive on meeting trees; adjust patterns to your repo).
is_fact_doc() {
  local p="$1"
  case "$p" in
    */memory/*|*/meetings/*) return 1 ;;
  esac
  case "$(basename "$p")" in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-*) return 1 ;;
  esac
  case "$p" in
    */rules/*.md|*/docs/rules-full/*.md|*SKILL.md|*playbook*.md|*runbook*.md|*soul.md|*CLAUDE.md|*AGENTS.md) return 0 ;;
    *) return 1 ;;
  esac
}

emit_guidance() {
  local files="$1" origin="$2" event="$3"
  GUIDE_FILES="$files" GUIDE_ORIGIN="$origin" GUIDE_EVENT="$event" python3 - <<'PYEOF2'
import json, os
ctx = f"""[copy-coherence {os.environ['GUIDE_ORIGIN']}] fact-document change detected: {os.environ['GUIDE_FILES']}
Copies of the same fact may be alive in other files - sweep this turn:
1. Take a content anchor (identifier/phrase you just changed) and run `git grep -n` across the skill tree + known deployment roots. Line-level (not -l); content anchors, never filename/path anchors.
2. Compare hits against the canonical source - the sweep gives you places to look, the canonical source gives the verdict.
3. Note the detection path ("what was caught" + "which check caught it").
4. If you fixed M of N copies: update the rest or plant a canonical pointer. Intentional asymmetry passes with one line: `copy-asymmetry: <reason>` in the commit/log.
(Coverage = copies sharing identifiers. Restated copies are below the verbatim threshold - the pre-send cross-review layer covers those.)"""
print(json.dumps({"hookSpecificOutput": {"hookEventName": os.environ['GUIDE_EVENT'], "additionalContext": ctx}}))
PYEOF2
}

if [ "$MODE" = "post-edit" ]; then
  FP=$(printf '%s' "$INPUT" | python3 -c "import json,sys
try: print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))
except Exception: pass" 2>/dev/null || true)
  [ -n "$FP" ] && is_fact_doc "$FP" && emit_guidance "$FP" "edit" "PostToolUse"
elif [ "$MODE" = "pre-commit" ]; then
  CMD=$(printf '%s' "$INPUT" | python3 -c "import json,sys
try: print(json.load(sys.stdin).get('tool_input',{}).get('command',''))
except Exception: pass" 2>/dev/null || true)
  case "$CMD" in
    *"git commit"*)
      ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
      STAGED=$([ -n "$ROOT" ] && git -C "$ROOT" diff --cached --name-only 2>/dev/null || true)
      # `git commit -a/-am/--all` commits unstaged tracked changes: --cached alone
      # goes silent there (measured) — union in worktree changes vs HEAD. A few
      # extra names cost nothing; the gate only routes, it never blocks.
      case " $CMD" in
        *" -a"*|*"--all"*)
          STAGED=$(printf '%s\n%s' "$STAGED" "$([ -n "$ROOT" ] && git -C "$ROOT" diff --name-only HEAD 2>/dev/null)" | sort -u) ;;
      esac
      HITS=""
      while IFS= read -r f; do
        [ -n "$f" ] && is_fact_doc "/$f" && HITS="${HITS}${f} "
      done <<< "$STAGED"
      [ -n "$HITS" ] && emit_guidance "$HITS" "pre-commit" "PreToolUse"
      ;;
  esac
fi
exit 0
