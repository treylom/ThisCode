#!/usr/bin/env bash
# rule-router.sh — UserPromptSubmit hook (Layer 1 enforcement; see docs/rules-system.md
#   "Enforcement: when the self-check gets skipped").
#
# Reads the prompt, matches task-type keywords, and force-surfaces the matching rule's
# core gate from rules/INDEX.md — so that a *skipped* INDEX self-check still applies.
# The mapping keys off task-types (it mirrors INDEX triggers; it does NOT duplicate rule bodies).
# Complementary to a static always-on self-check (which gets tuned out by being identical
# every turn) — this one is situation-matched, so it is relevant and hard to ignore.
#
# fail-open: no jq / empty prompt / no keyword match → emit nothing, exit 0. Never blocks.
#
# Register (~/.claude/settings.json) under UserPromptSubmit — see commands/install-hooks.md:
#   {"type":"command","command":"bash ~/.claude/plugins/thiscode/hooks/rule-router.sh","timeout":3}
command -v jq >/dev/null 2>&1 || exit 0
INPUT="$(cat 2>/dev/null || true)"
P="$(printf '%s' "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || true)"
[ -n "$P" ] || exit 0

m() { printf '%s' "$P" | grep -iqE "$1"; }
GATES=()

# search / absence claim → source-fact + search-usage + knowledge-retrieval
m 'search|find\b|where.{0,4}(is|are)|missing|empty|exists?|not ?found|검색|찾[아어]|어디.{0,3}있|없[다어는음을지]|비어|존재' && GATES+=(\
"🔴 [search / absence] source-fact: no source → no assertion · don't single-grep (multi-axis cross-check) · code-quality: don't conclude 'absent' from limited observation (expand limit/boundary first). search-usage: 3–7 word query, trust defaults, rephrase once before fallback. knowledge-retrieval: search the KB before planning / concluding absent.")

# deploy / public-repo / port / MCP → porting-infra (+ autonomy §1)
m 'deploy|push\b|publish|release|\bship\b|merge|MCP|port(ing)?|배포|푸시|릴리스|공개' && GATES+=(\
"🔴 [deploy / public] porting-infra: check upstream before hand-rolling · secret-scan before ANY push · smoke green before push · MCP health-check. autonomy §1: public-repo change = user approval.")

# delegate / meeting / multi-agent → orchestration + meeting-protocol
m 'delegat|dispatch|hand ?off|assign|meeting|collaborat|multi-?agent|위임|시키|맡기|회의|협업|멀티에이전트|함께.{0,4}(분석|작업|검토)|같이.{0,4}(분석|작업|검토)' && GATES+=(\
"🔴 [delegate / meeting] orchestration: spell out HOW completely in the FIRST dispatch message; verify bot identity (don't assume). meeting-protocol: dedicated thread + verify the dispatched bot actually started (ack ≠ execution) before ending the turn.")

# completion / delivery → autonomy + code-quality
m 'done\b|finish|complete|deliver|submit|wrap ?up|완료|마감|납품|제출' && GATES+=(\
"🔴 [done / deliver] autonomy §2: before declaring 'done' to the user, pre-report to the completion channel. code-quality: run the 3-step verification after a fix; verified-execution > eyeballed code.")

# build / design / debug / verify → skill-process + code-quality
m 'build|design|implement|scaffold|debug|fix\b|verif|\btest\b|버그|디버그|구현|설계|검증' && GATES+=(\
"🔴 [build / debug / verify] skill-process: invoke the relevant skill BEFORE responding · design before implement (unless user said proceed) · root cause before fix. code-quality: reproduce → fix → prove.")

[ ${#GATES[@]} -eq 0 ] && exit 0
printf '🚨 Situation-matched rule gates — surfaced for application (rule-router · keyed off rules/INDEX.md):\n'
for g in "${GATES[@]}"; do printf -- '%s\n' "$g"; done
exit 0
