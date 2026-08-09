#!/usr/bin/env bash
# bot-session-init.sh — 봇 세션 SessionStart hook
#
# soul.md (페르소나) + WD-specific memory + 공통 규율을 SessionStart 시 자동 inject.
# 순정 Claude Code 환경 호환 — vault 없어도 동작.
#
# 사용 (~/.claude/settings.json):
#   "hooks": {
#     "SessionStart": [
#       {
#         "matcher": "",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "bash ~/.claude/plugins/thiscode/hooks/bot-session-init.sh",
#             "timeout": 10
#           }
#         ]
#       }
#     ]
#   }
#
# 봇 이름 자동 detect:
#   1. 명시 인자: `bot-session-init.sh <bot-name>`
#   2. DISCORD_STATE_DIR 환경변수 (e.g. ~/.claude/channels/discord-reviewer → reviewer)
#   3. 둘 다 없으면 무음 종료 (일반 개발 세션 — dev 간섭 방지)

set -uo pipefail

BOT="${1:-}"

# 인자 없으면 DISCORD_STATE_DIR 에서 자동 추출
if [ -z "$BOT" ]; then
  if [ -z "${DISCORD_STATE_DIR:-}" ]; then
    exit 0
  fi
  _state_base=$(basename "$DISCORD_STATE_DIR")
  case "$_state_base" in
    discord)
      # 순정 discord 플러그인 dir (per-bot suffix 없음) = per-bot 세션 아님.
      # discord-discord/soul.md MISSING 오주입 대신 무음 종료 (L26 철학 동일).
      exit 0
      ;;
    discord-*)
      BOT=${_state_base#discord-}
      ;;
    *)
      BOT=$_state_base
      ;;
  esac
fi

if [ -z "$BOT" ]; then
  exit 0
fi

SOUL_FILE="$HOME/.claude/channels/discord-${BOT}/soul.md"

# WD → Claude Code projects 경로 인코딩.
# Claude Code 는 비영숫자 전부를 - 로 치환 (공백·_·.·한글 포함). 예:
#   /home/me/My_App/v1.0  →  -home-me-My-App-v1-0
#   (`/`·`_`·`.`·공백 → -, 기존 `-` 는 유지)
# 구 `s|/|-|g; s|_|-|g` 는 공백·.·한글 미치환 → 네이티브 memory 위치와 분기.
WD_ENCODED=$(echo "$PWD" | sed 's|[^a-zA-Z0-9]|-|g')
MEM_DIR="$HOME/.claude/projects/${WD_ENCODED}/memory"
MEM_INDEX="$MEM_DIR/MEMORY.md"

# 공유 메모리 인덱스 detect (사용자 환경별 분기)
#   1. CLAUDE_DISCODE_VAULT 환경변수 (vault 사용자 설정)
#   2. $HOME/.thiscode/shared-memory/ (vault 없는 사용자 default)
#   3. $PWD/shared-memory/ (claude-discode workspace-local 관행 — env 없을 때)
SHARED_INDEX=""
if [ -n "${CLAUDE_DISCODE_VAULT:-}" ] && [ -f "${CLAUDE_DISCODE_VAULT}/.claude-memory/shared/SHARED-INDEX.md" ]; then
  SHARED_INDEX="${CLAUDE_DISCODE_VAULT}/.claude-memory/shared/SHARED-INDEX.md"
elif [ -f "$HOME/.thiscode/shared-memory/SHARED-INDEX.md" ]; then
  SHARED_INDEX="$HOME/.thiscode/shared-memory/SHARED-INDEX.md"
elif [ -f "$PWD/shared-memory/SHARED-INDEX.md" ]; then
  SHARED_INDEX="$PWD/shared-memory/SHARED-INDEX.md"
fi

SECTIONS=""

# --- 0.5) rules-seed staleness check (B3, PRD 59-pm-prd-night-batch 기준 4·5) ---
# boot-time WARN only — never auto-merges, never auto-updates the bot's own
# copy-once rules-seed.md (create-bot Step 6 owns the copy; this hook only
# compares version stamps). ThisCode has no static per-bot launch script
# (claude is started directly — see create-bot Step 7), so this SessionStart
# hook is the actual "every boot" checkpoint (ThisCodex equivalent:
# infra-launch.sh). Emitted to stderr, not stdout, so it never corrupts the
# JSON hookSpecificOutput contract this hook prints below.
_BOT_WD_EFF="${BOT_WD:-$PWD}"
_HOOK_SELF="${BASH_SOURCE[0]:-$0}"
_HOOK_DIR="$(cd "$(dirname "$_HOOK_SELF")" 2>/dev/null && pwd)"
_PLUGIN_ROOT="$([ -n "$_HOOK_DIR" ] && cd "$_HOOK_DIR/.." 2>/dev/null && pwd)"
if [ -n "$_PLUGIN_ROOT" ] && [ -f "${_BOT_WD_EFF}/rules-seed.md" ] && [ -f "${_PLUGIN_ROOT}/templates/rules-seed.md" ]; then
  _BOT_RULES_VER=$(command grep -oE 'rules-seed v[0-9.]+' "${_BOT_WD_EFF}/rules-seed.md" | head -1 | awk '{print $2}')
  _PRODUCT_RULES_VER=$(command grep -oE 'rules-seed v[0-9.]+' "${_PLUGIN_ROOT}/templates/rules-seed.md" | head -1 | awk '{print $2}')
  if [ -n "$_BOT_RULES_VER" ] && [ -n "$_PRODUCT_RULES_VER" ] && [ "$_BOT_RULES_VER" != "$_PRODUCT_RULES_VER" ]; then
    echo "[thiscode][WARN] rules-seed $_BOT_RULES_VER -> $_PRODUCT_RULES_VER available — update by explicit command only" >&2
  fi
fi

# --- 1) soul.md (페르소나·말투 규율) ---
if [ -f "$SOUL_FILE" ]; then
  SOUL_CONTENT=$(cat "$SOUL_FILE")
  SECTIONS+="=== [${BOT}] soul.md — 페르소나·말투 규율 ===

${SOUL_CONTENT}

"
else
  SECTIONS+="=== [${BOT}] soul.md: MISSING at ${SOUL_FILE} ===
봇 페르소나 파일 미발견. thiscode wizard 로 다시 생성하거나 직접 작성.
template 위치: <thiscode>/templates/soul-*.md

"
fi

# --- 2) WD 전용 메모리 인덱스 ---
if [ -f "$MEM_INDEX" ]; then
  MEM_CONTENT=$(cat "$MEM_INDEX")
  SECTIONS+="=== [${BOT}] WD memory 인덱스 (${MEM_DIR}) ===

${MEM_CONTENT}

상세 파일은 Read 도구로 접근. 새 memory (봇 개성·어투·실수 복기) 는 이 디렉토리에 작성.

"
else
  SECTIONS+="=== [${BOT}] WD memory: 미생성 (${MEM_DIR}) ===
첫 학습 시 본 경로에 memory 파일 + MEMORY.md 인덱스 신규 생성.

"
fi

# --- 3) 공유 메모리 인덱스 (해당 시) ---
if [ -n "$SHARED_INDEX" ]; then
  SHARED_CONTENT=$(head -100 "$SHARED_INDEX")
  SECTIONS+="=== [${BOT}] shared memory 인덱스 (${SHARED_INDEX}) ===

${SHARED_CONTENT}

위 인덱스 따라 fetch. 모든 봇·머신 공유 사실은 이 디렉토리.

"
fi

# --- 3.5) Active meeting + progressive rules router (optional) ---
# Generic distribution contract: derive from env/BOT_WD/PWD, never from a
# maintainer-only vault path. Missing files are a graceful no-op.
MEETING_DIR="${MEETING_PROTOCOL_DIR:-}"
if [ -z "$MEETING_DIR" ] && [ -n "${BOT_WD:-}" ]; then
  MEETING_DIR="${BOT_WD}/meetings"
fi
if [ -z "$MEETING_DIR" ]; then
  MEETING_DIR="${PWD}/meetings"
fi
ACTIVE_MEETING="${MEETING_ACTIVE_FILE:-${MEETING_DIR}/ACTIVE.md}"
if [ -f "$ACTIVE_MEETING" ]; then
  MEETING_CONTENT=$(cat "$ACTIVE_MEETING")
  SECTIONS+="=== active meeting protocol (${ACTIVE_MEETING}) ===

${MEETING_CONTENT}

Use meeting-protocol.md for dispatch verification, KST timestamps, and progress-file updates.

"
fi

RULES_DIR="${RULES_DIR:-}"
if [ -z "$RULES_DIR" ] && [ -n "${BOT_WD:-}" ]; then
  RULES_DIR="${BOT_WD}/rules"
fi
if [ -z "$RULES_DIR" ]; then
  RULES_DIR="${PWD}/rules"
fi
RULES_INDEX="${RULES_DIR}/INDEX.md"
if [ -f "$RULES_INDEX" ]; then
  RULES_CONTENT=$(cat "$RULES_INDEX")
  SECTIONS+="=== progressive rules INDEX (${RULES_INDEX}) ===

${RULES_CONTENT}

Load rules/meeting-protocol.md when coordinating meetings or dispatch verification.

"
fi

# --- 4) 세션 공통 필수 규율 ---
SECTIONS+='=== 필수 규율 (매 응답 자가 점검) ===
1. 위 soul.md 페르소나·말투를 매 응답에 유지. 사용자 지적 전 자가 점검.
2. Discord 메시지가 "/" 로 시작 + 두번째 문자가 영문 → 슬래시 커맨드. 즉시 Skill 도구로 호출, 다른 응답 금지. 스킬 없으면 "Unknown skill: /xxx" 짧게 회신.
3. 메모리 쓰기 분기:
   - 봇 개성·어투·실수 복기 → WD memory (위 경로)
   - 공용 사실·도메인 → shared memory (위 인덱스)
4. 외부 채널 응답 (Discord) — 터미널 출력만 X. mcp__plugin_discord_discord__reply 등 도구 우선.

'

# JSON 인코딩 — 특수문자 안전. Windows(Git Bash)엔 python3 이름이 없고
# WindowsApps 스토어 스텁이 걸릴 수 있어 python3 → python → bun → node 폴백.
_PY=""
for _c in python3 python; do
  _p="$(command -v "$_c" 2>/dev/null || true)"
  case "$_p" in ''|*WindowsApps*) continue;; esac
  _PY="$_p"; break
done
export SECTIONS
if [ -n "$_PY" ]; then
"$_PY" -c '
import json, os
content = os.environ["SECTIONS"]
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": content
    }
}))
'
elif command -v bun >/dev/null 2>&1; then
  bun -e 'console.log(JSON.stringify({hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:process.env.SECTIONS}}))'
elif command -v node >/dev/null 2>&1; then
  node -e 'console.log(JSON.stringify({hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:process.env.SECTIONS}}))'
fi

# ----------------------------------------------------------------------
# (옵션) Memory Load Audit — 로드된 memory 의 checksum 기록
# 분석용. audit 실패해도 hook 자체는 성공.
# ----------------------------------------------------------------------
{
  AUDIT_DIR="$HOME/.claude/audit/memory-load"
  mkdir -p "$AUDIT_DIR" 2>/dev/null
  AUDIT_FILE="$AUDIT_DIR/${BOT}-$(date -u +%Y-%m-%dT%H-%M-%S).json"
  export AUDIT_BOT="$BOT" AUDIT_FILE AUDIT_SOUL="$SOUL_FILE" AUDIT_MEM="$MEM_INDEX" AUDIT_SHARED="$SHARED_INDEX"
  [ -n "$_PY" ] && "$_PY" -c '
import json, os, hashlib, datetime
def stat(p):
    if not p or not os.path.isfile(p): return None
    try:
        with open(p, "rb") as f: data = f.read()
        return {"path": p, "lines": data.count(b"\n"), "checksum": hashlib.sha1(data).hexdigest()[:8]}
    except Exception: return None
dump = {
    "bot": os.environ.get("AUDIT_BOT", ""),
    "session_started": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "cwd": os.environ.get("PWD", ""),
    "loaded": {
        "soul": stat(os.environ.get("AUDIT_SOUL", "")),
        "wd_memory_index": stat(os.environ.get("AUDIT_MEM", "")),
        "shared_memory_index": stat(os.environ.get("AUDIT_SHARED", "")),
    },
}
with open(os.environ["AUDIT_FILE"], "w") as f:
    json.dump(dump, f, indent=2, ensure_ascii=False)
' 2>/dev/null
} 2>/dev/null || true

exit 0
