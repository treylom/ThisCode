#!/bin/bash
# Skill / sub-agent scope name-collision check.
#
# Why this exists: skills and sub-agents resolve same-name collisions in
# OPPOSITE directions (skills: personal wins · sub-agents: project wins), so a
# personal skill can silently disable a project rule skill with no warning.
#
# Positive control is built in on purpose: if either side counts zero, this
# reports a FAILED CHECK rather than "no collisions". A broken path must never
# read as a clean bill of health.
#
# Usage: scope-collision-check.sh [project-root]   (default: $PWD)
P="${1:-$PWD}"
US=~/.claude/skills; PS="$P/.claude/skills"
UA=~/.claude/agents; PA="$P/.claude/agents"
sk_u=$(ls -d "$US"/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')
sk_p=$(ls -d "$PS"/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')
ag_u=$(grep -h '^name:' "$UA"/*.md 2>/dev/null | wc -l | tr -d ' ')
ag_p=$(grep -h '^name:' "$PA"/*.md 2>/dev/null | wc -l | tr -d ' ')
echo "totals (positive control): skill user=$sk_u project=$sk_p | agent user=$ag_u project=$ag_p"
if [ "$sk_u" -eq 0 ] || [ "$sk_p" -eq 0 ] || [ "$ag_u" -eq 0 ] || [ "$ag_p" -eq 0 ]; then
  echo "FAILED CHECK — one side counted zero. Verify paths/layout before trusting this."
  echo "Do NOT read this as 'no collisions'."
  exit 2
fi
skc=$(comm -12 <(ls -d "$US"/*/SKILL.md 2>/dev/null | xargs -n1 dirname | xargs -n1 basename | sort) \
               <(ls -d "$PS"/*/SKILL.md 2>/dev/null | xargs -n1 dirname | xargs -n1 basename | sort))
agc=$(comm -12 <(grep -h '^name:' "$UA"/*.md 2>/dev/null | sed 's/^name: *//' | sort -u) \
               <(grep -h '^name:' "$PA"/*.md 2>/dev/null | sed 's/^name: *//' | sort -u))
[ -n "$skc" ] && { echo "COLLISION (skills — personal wins, project rule skill is shadowed):"; echo "$skc" | sed 's/^/   /'; }
[ -n "$agc" ] && { echo "COLLISION (sub-agents — project wins):"; echo "$agc" | sed 's/^/   /'; }
[ -z "$skc" ] && [ -z "$agc" ] && echo "OK — no collisions (totals verified, so this zero is meaningful)"
exit 0
