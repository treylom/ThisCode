#!/bin/bash
# verify-before-push.sh — PreToolUse hook (A1, matcher Bash): git push/commit · gh pr create|merge
#   직전에 세션 내 verify(test/build/lint/diff 등) 기록이 없으면 검증 누락으로 판단.
#
# ⚠️ 모드 (fleet-wide BLOCK 의 무인 위험 회피):
#   - 기본 = OBSERVE(log-only): would-be-deny 를 audit 에만 기록하고 통과(allow). 봇 차단 0.
#   - HARD ENFORCE = env A1_ENFORCE=1 또는 flag 파일 .claude/hooks/.a1-enforce 존재 시 → 실제 deny.
#   (maintainer 가 아침에 audit 의 'OBSERVE(would-deny' 기록을 검토 → false-positive 없으면 enforce 전환.)
#
# 근거: 04-synthesis A1(9891줄 삭제 near-miss ★★) / feedback_never_batch_verify_with_dependent_commit.
# 자동화(aktofu) 파이프라인 push 는 신뢰 → skip. fail-open(판단 불확실 시 allow).
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/hookkit.sh"
hk_failopen
hk_read_input
[ "$(hk_json '.tool_name')" = "Bash" ] || hk_allow
hk_is_automation && hk_allow
CMD="$(hk_json '.tool_input.command')"
[ -n "$CMD" ] || hk_allow
# push/commit/pr 명령만 대상 (rtk/proxy wrapper 포함 — ' git commit' 부분일치)
echo "$CMD" | grep -qE '(^|[;&| ])git[[:space:]]+(push|commit)|gh[[:space:]]+pr[[:space:]]+(create|merge)' || hk_allow

# transcript 에서 직전 verify 기록 검사
TRANSCRIPT="$(hk_transcript)"
HAS_VERIFY=unknown
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ] && command -v python3 >/dev/null 2>&1; then
  HAS_VERIFY="$(TR="$TRANSCRIPT" python3 2>/dev/null <<'PY'
import json, os, re
VERIFY = re.compile(r"\b(test|pytest|vitest|jest|tsc|build|lint|py_compile|cargo|go test|npm|run-hook-tests|playwright)\b|git\s+diff|\bdiff\b")
PUSH = re.compile(r"(^|[;&| ])git\s+(push|commit)|gh\s+pr\s+(create|merge)")
path = os.environ["TR"]
try:
    lines = open(path, encoding="utf-8").read().splitlines()
except OSError:
    print("unknown"); raise SystemExit(0)
cmds = []
for ln in lines:
    ln = ln.strip()
    if not ln: continue
    try: m = json.loads(ln)
    except Exception: continue
    if m.get("type") != "assistant": continue
    content = (m.get("message", {}) or {}).get("content")
    if not isinstance(content, list): continue
    for b in content:
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
            cmds.append(str((b.get("input", {}) or {}).get("command", "")))
cmds = cmds[-40:]
has = any(VERIFY.search(c) and not PUSH.search(c) for c in cmds)
print("yes" if has else "no")
PY
)" || HAS_VERIFY=unknown
fi

# fail-open: verify 있음/판단 불확실 → allow
case "$HAS_VERIFY" in
  yes|unknown|"") hk_allow ;;
esac

# 여기 도달 = push/commit 인데 직전 verify 기록 없음.
ENFORCE=no
[ "${A1_ENFORCE:-}" = "1" ] && ENFORCE=yes
[ -f "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.a1-enforce" ] && ENFORCE=yes
if [ "$ENFORCE" = "yes" ]; then
  hk_log "A1 ENFORCE deny: '$CMD'"
  hk_deny "검증 없이 push/commit 하려 합니다(A1). 이번 세션에 직전 테스트/빌드/diff 등 검증 기록이 없습니다. verify 먼저 돌려 GREEN 확인 후 push/commit 하세요. (검증 명령을 먼저 실행하면 통과합니다.)"
else
  hk_log "A1 OBSERVE(would-deny, allowed): '$CMD'"
  hk_allow
fi
