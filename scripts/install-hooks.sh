#!/usr/bin/env bash
# install-hooks.sh — ThisCode 훅을 사용자 settings.json 에 «안전하게» 병합한다.
#
# 왜 스크립트인가: 이 병합 로직이 지금까지 `skills/install-hooks/SKILL.md` 안에만
#   산문으로 있었다. 그래서 create-bot 은 같은 일을 하려면 «베껴야» 했고, 베낀 사본은
#   원본이 고쳐질 때 같이 안 고쳐진다. 두 곳이 같은 파일을 부르게 만들어 그 갈라짐을 없앤다.
#
# 왜 --verify 인가: 「설치됐나」는 install-gate.sh 가 답할 수 없는 질문이다(그 게이트는
#   「시도 없이 수동 안내를 띄워도 되나」에만 답한다). 설치 여부는 설치기 자신이 답한다.
#
# 사용:
#   bash scripts/install-hooks.sh [--home <dir>] [--plugin-dir <dir>] [--dry-run]
#       훅을 병합한다. 기존 훅은 보존하고 같은 명령은 중복 추가하지 않는다.
#   bash scripts/install-hooks.sh --verify [--home <dir>] [--plugin-dir <dir>]
#       병합하지 않고 «검사만» 한다. exit 0 = 4 이벤트 + 필수 훅 전부 등록 + 명령 경로 실재.
#       exit 1 = 빠진 항목을 줄마다 출력한다.
#
# 종료코드: 0 성공 / 1 검사 실패(--verify) / 2 전제 불충족(jq·node 둘 다 없음, 인자 오류)
#
# 이식성: bash 3.2(macOS 기본)에서 동작한다 — 연관배열·mapfile 쓰지 않는다.
#   병합 엔진은 jq 를 먼저 쓰고, 없으면 node 로 «같은 규칙»을 수행한다(Windows 등 jq 부재 환경).
#   node 는 이 제품의 시험 러너라 사실상 항상 있다. 둘 다 없을 때만 멈춘다.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$HERE/.." && pwd)"
HOME_DIR="${HOME:-}"
DRY_RUN=0
VERIFY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --home)        HOME_DIR="${2:-}"; shift 2 ;;
    --plugin-dir)  PLUGIN_DIR="${2:-}"; shift 2 ;;
    --dry-run)     DRY_RUN=1; shift ;;
    --verify)      VERIFY=1; shift ;;
    -h|--help)     command sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "install-hooks: 모르는 인자 — $1" >&2; exit 2 ;;
  esac
done

if [ -z "$HOME_DIR" ]; then
  echo "install-hooks: 홈 디렉터리를 알 수 없다 — --home <dir> 로 지정할 것" >&2
  exit 2
fi

SETTINGS="$HOME_DIR/.claude/settings.json"

# 등록돼 있어야 하는 훅. 이 목록이 --verify 의 «기대값»이다.
REQUIRED_HOOKS="bot-session-init.sh discord-slash-cmd.sh regression-self-check.sh rule-router.sh dispatch-room-gate.py meeting-stop-reread.sh reply-gate.sh"

# ── 병합 엔진 선택 ──────────────────────────────────────────────────
_engine() {
  if command -v jq >/dev/null 2>&1; then echo jq
  elif command -v node >/dev/null 2>&1; then echo node
  else echo none; fi
}

# settings.json 에 등록된 hook 명령 문자열을 «한 줄에 하나씩» 뱉는다.
_list_commands() {
  [ -f "$1" ] || return 0
  case "$(_engine)" in
    jq)
      jq -r '.hooks // {} | to_entries[] | .value[]? | .hooks[]? | .command // empty' "$1" 2>/dev/null
      ;;
    node)
      node -e 'const fs=require("fs");let j={};try{j=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));}catch(e){process.exit(0);}for(const ev of Object.keys(j.hooks||{}))for(const g of j.hooks[ev]||[])for(const h of g.hooks||[])if(h.command)console.log(h.command);' "$1" 2>/dev/null
      ;;
    *) return 0 ;;
  esac
}

# 이벤트에 실제로 훅이 1개 이상 달려 있는가
_event_present() {
  [ -f "$1" ] || return 1
  case "$(_engine)" in
    jq)
      n="$(jq -r --arg e "$2" '((.hooks // {})[$e] // []) | map(.hooks // []) | flatten | length' "$1" 2>/dev/null)"
      [ -n "$n" ] && [ "$n" -gt 0 ] 2>/dev/null
      ;;
    node)
      node -e 'const fs=require("fs");let j={};try{j=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));}catch(e){process.exit(1);}const g=(j.hooks||{})[process.argv[2]]||[];let n=0;for(const x of g)n+=(x.hooks||[]).length;process.exit(n>0?0:1);' "$1" "$2" 2>/dev/null
      ;;
    *) return 1 ;;
  esac
}

# 명령 문자열에서 스크립트 경로만 뽑는다: bash '<경로>' / python3 '<경로>'
_path_of() { printf '%s' "$1" | command sed -n "s/^[^']*'\([^']*\)'.*$/\1/p"; }

# ── --verify: 머지 없이 검사만 ──────────────────────────────────────
if [ "$VERIFY" -eq 1 ]; then
  if [ "$(_engine)" = "none" ]; then
    echo "install-hooks: jq 도 node 도 없어 설정 파일을 읽을 수 없다 — 둘 중 하나를 설치할 것" >&2
    exit 2
  fi
  if [ ! -f "$SETTINGS" ]; then
    echo "빠짐 — 설정 파일이 없다: $SETTINGS"
    echo "검사 실패 — 훅이 하나도 등록돼 있지 않다."
    exit 1
  fi
  missing=0
  cmds="$(_list_commands "$SETTINGS")"
  for ev in SessionStart UserPromptSubmit PreToolUse Stop; do
    if ! _event_present "$SETTINGS" "$ev"; then
      echo "빠짐 — 이벤트에 등록된 훅이 없다: $ev"
      missing=$((missing + 1))
    fi
  done
  for want in $REQUIRED_HOOKS; do
    if ! printf '%s\n' "$cmds" | command grep -q -- "$want"; then
      echo "빠짐 — 훅이 등록돼 있지 않다: $want"
      missing=$((missing + 1))
    fi
  done
  # 등록은 됐는데 «파일이 실재하지 않는» 경우 — 조용한 무반응의 원인이라 따로 잡는다.
  oldifs="$IFS"; IFS='
'
  for c in $cmds; do
    [ -z "$c" ] && continue
    p="$(_path_of "$c")"
    [ -z "$p" ] && continue
    case "$p" in
      *"/hooks/"*)
        if [ ! -f "$p" ]; then
          echo "빠짐 — 등록된 명령의 파일이 실재하지 않는다: $p"
          missing=$((missing + 1))
        fi
        ;;
    esac
  done
  IFS="$oldifs"
  if [ "$missing" -gt 0 ]; then
    echo "검사 실패 — 빠진 항목 $missing 건. 병합하려면: bash scripts/install-hooks.sh --home \"$HOME_DIR\""
    exit 1
  fi
  echo "검사 통과 — 4 이벤트 + 필수 훅 전부 등록돼 있고 명령 파일도 실재한다 ($SETTINGS)"
  exit 0
fi

# ── 병합 ────────────────────────────────────────────────────────────
ENGINE="$(_engine)"
if [ "$ENGINE" = "none" ]; then
  echo "install-hooks: 병합에는 jq 또는 node 가 필요한데 둘 다 없다." >&2
  echo "  jq(macOS: brew install jq · Debian: apt-get install jq) 또는 Node.js 를 설치한 뒤 다시 실행할 것." >&2
  exit 2
fi

PATCH=$(cat <<EOF
{
  "hooks": {
    "SessionStart": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "bash '$PLUGIN_DIR/hooks/bot-session-init.sh'", "timeout": 10 }
      ] }
    ],
    "UserPromptSubmit": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "bash '$PLUGIN_DIR/hooks/discord-slash-cmd.sh'", "timeout": 5 },
        { "type": "command", "command": "bash '$PLUGIN_DIR/hooks/regression-self-check.sh'", "timeout": 3 },
        { "type": "command", "command": "bash '$PLUGIN_DIR/hooks/rule-router.sh'", "timeout": 3 }
      ] }
    ],
    "PreToolUse": [
      { "matcher": "mcp__plugin_discord_discord__reply|mcp__plugin_discord_discord__edit_message", "hooks": [
        { "type": "command", "command": "python3 '$PLUGIN_DIR/hooks/dispatch-room-gate.py'", "timeout": 5 }
      ] }
    ],
    "Stop": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "bash '$PLUGIN_DIR/hooks/meeting-stop-reread.sh'", "timeout": 5 },
        { "type": "command", "command": "bash '$PLUGIN_DIR/hooks/reply-gate.sh'", "timeout": 5 }
      ] }
    ]
  }
}
EOF
)

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[미리보기] 병합 대상: $SETTINGS (엔진 $ENGINE)"
  echo "[미리보기] 추가될 훅:"
  printf '%s\n' "$PATCH" | command grep -o "hooks/[A-Za-z0-9._-]*" | sort -u | command sed 's/^/  - /'
  echo "[미리보기] 파일은 바꾸지 않았다."
  exit 0
fi

mkdir -p "$HOME_DIR/.claude" || { echo "install-hooks: $HOME_DIR/.claude 를 만들 수 없다" >&2; exit 2; }
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"

# 백업 — 되돌릴 수 있어야 손대도 되는 것이다.
BACKUP="$SETTINGS.bak-$(date +%s)"
cp "$SETTINGS" "$BACKUP" 2>/dev/null || true

# 순서 보존 병합: matcher별 그룹 유지(등장 순), 내부 hook 은 type+command+timeout 으로 첫 등장만.
# 규칙은 jq·node 두 경로가 «같다» — 한쪽만 고치면 환경에 따라 결과가 갈린다.
if [ "$ENGINE" = "jq" ]; then
  printf '%s' "$PATCH" > "$SETTINGS.patch.tmp"
  jq -s 'def uniqHooks: reduce .[] as $x ([]; if (map(.type == $x.type and .command == $x.command and .timeout == $x.timeout) | any) then . else . + [$x] end);
def mergeEv($a; $b):
  reduce (($a + $b) | .[]) as $g ({order: [], map: {}};
    (($g.matcher // "")) as $m
    | if (.map | has($m)) then (.map[$m].hooks += ($g.hooks // []))
      else (.order += [$m] | .map[$m] = ($g + {matcher: $m, hooks: ($g.hooks // [])})) end)
  | [ .map[.order[]] | (.hooks |= uniqHooks) ];
. as [$s, $p] | ($s * $p)
| .hooks.SessionStart     = mergeEv($s.hooks.SessionStart // [];     $p.hooks.SessionStart // [])
| .hooks.UserPromptSubmit = mergeEv($s.hooks.UserPromptSubmit // []; $p.hooks.UserPromptSubmit // [])
| .hooks.Stop             = mergeEv($s.hooks.Stop // [];             $p.hooks.Stop // [])
| .hooks.PreToolUse       = mergeEv($s.hooks.PreToolUse // [];       $p.hooks.PreToolUse // [])' \
    "$SETTINGS" "$SETTINGS.patch.tmp" > "$SETTINGS.tmp"
  rc=$?
  rm -f "$SETTINGS.patch.tmp"
  if [ $rc -ne 0 ]; then rm -f "$SETTINGS.tmp"; echo "install-hooks: 병합 실패(jq)" >&2; exit 2; fi
else
  node -e 'const fs=require("fs");
const a = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const b = JSON.parse(process.argv[2]);
const merged = { ...a, hooks: { ...(a.hooks || {}) } };
for (const ev of ["SessionStart", "UserPromptSubmit", "Stop", "PreToolUse"]) {
  const groups = new Map();
  for (const g of [...((a.hooks || {})[ev] || []), ...((b.hooks || {})[ev] || [])]) {
    const m = g.matcher || "";
    if (!groups.has(m)) groups.set(m, Object.assign({}, g, { matcher: m, hooks: [] }));
    const tgt = groups.get(m);
    for (const h of g.hooks || []) {
      const k = [h.type, h.command, h.timeout].join("|");
      if (!tgt.hooks.some(x => [x.type, x.command, x.timeout].join("|") === k)) tgt.hooks.push(h);
    }
  }
  if (groups.size) merged.hooks[ev] = Array.from(groups.values());
}
fs.writeFileSync(process.argv[3], JSON.stringify(merged, null, 2));' "$SETTINGS" "$PATCH" "$SETTINGS.tmp"
  if [ $? -ne 0 ]; then rm -f "$SETTINGS.tmp"; echo "install-hooks: 병합 실패(node)" >&2; exit 2; fi
fi

mv "$SETTINGS.tmp" "$SETTINGS"
echo "훅 병합 완료 — $SETTINGS (엔진 $ENGINE · 백업 $BACKUP)"
echo "검사하려면: bash scripts/install-hooks.sh --verify --home \"$HOME_DIR\""
