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
#   모드는 파일 하나가 정한다: 플러그인 루트에 hooks/hooks.json 이 있으면 Claude Code 가
#   훅을 «직접» 싣는다(플러그인 모드). 그때 이 스크립트는 병합하지 않고, 옛 병합 방식으로
#   settings.json 에 남아 있던 «같은» 훅만 지운다(이중 발화 차단) + 검사한다.
#   hooks.json 이 없으면 예전 그대로 settings.json 에 병합한다(병합 모드).
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
    --home)        [ $# -ge 2 ] || { echo "install-hooks: $1 에 값이 없다" >&2; exit 2; }
                   HOME_DIR="${2:-}"; shift 2 ;;
    --plugin-dir)  [ $# -ge 2 ] || { echo "install-hooks: $1 에 값이 없다" >&2; exit 2; }
                   PLUGIN_DIR="${2:-}"; shift 2 ;;
    --dry-run)     DRY_RUN=1; shift ;;
    --verify)      VERIFY=1; shift ;;
    -h|--help)     command sed -n '2,25p' "${BASH_SOURCE[0]}"; exit 0 ;;
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

# 명령 문자열에서 스크립트 경로만 뽑는다: bash '<경로>' / python3 "<경로>" / bash <경로>
#   첫 토큰(실행기) 뒤의 «첫 인자» 하나만 본다. 세 형태(작은따옴표·큰따옴표·무따옴표)를 다 받는다 —
#   한 형태만 보면 나머지는 «경로 없음» 이 돼 뒤따르는 판정이 통째로 건너뛰어진다.
#   $HOME 같은 변수는 전개하지 않는다(전개하면 남의 홈을 우리 것으로 읽는다).
_path_of() {
  _rest="$(printf '%s' "$1" | command sed -n '1s/^[[:space:]]*[^[:space:]]*[[:space:]]*//p')"
  case "$_rest" in
    "'"*) printf '%s' "$_rest" | command sed -n "1s/^'\([^']*\)'.*$/\1/p" ;;
    '"'*) printf '%s' "$_rest" | command sed -n '1s/^"\([^"]*\)".*$/\1/p' ;;
    *)    printf '%s' "$_rest" | command sed -n '1s/^\([^[:space:]]*\).*$/\1/p' ;;
  esac
}

# ── 플러그인 모드 판정 ──────────────────────────────────────────────
# 플러그인 루트에 hooks/hooks.json 이 있으면 Claude Code 가 그 파일을 읽어 훅을 «직접»
#   싣는다(공식 플러그인과 같은 규약 — plugin.json 에 따로 선언하지 않는다). 그러면 이
#   스크립트가 할 일은 병합이 아니라 «옛 병합 잔존 정리 + 검사» 다.
# hooks.json 이 없으면 아래 병합 경로가 예전 그대로 돈다 — 되돌리기는 그 파일 하나를
#   지우는 것으로 끝난다.
HOOKS_JSON="$PLUGIN_DIR/hooks/hooks.json"
BOT_ONLY="$PLUGIN_DIR/hooks/lib/bot-only.sh"
PLUGIN_MODE=0
[ -f "$HOOKS_JSON" ] && PLUGIN_MODE=1

# JSON 으로 읽히는가 — 파싱 실패를 «훅 0개» 로 오독하지 않게 따로 묻는다.
_json_ok() {
  [ -f "$1" ] || return 1
  case "$(_engine)" in
    jq)   jq -e . "$1" >/dev/null 2>&1 ;;
    node) node -e 'const fs=require("fs");try{JSON.parse(fs.readFileSync(process.argv[1],"utf8"));}catch(e){process.exit(1);}' "$1" >/dev/null 2>&1 ;;
    *) return 1 ;;
  esac
}

# 옛 병합 잔존 = settings.json 안에서 «이 제품의 훅 파일명»(REQUIRED_HOOKS 7개)을
#   `/hooks/<이름>`(Windows 는 `\hooks\<이름>`) 꼴로 가리키는 명령. 자를 «경로»가 아니라 «파일명»으로 잡는 이유:
#   마켓 설치는 버전 디렉터리(…/thiscode/1.2.7/hooks/…)에 살아서, 1.3.0 으로 올린 뒤의
#   PLUGIN_DIR 과 옛 항목의 경로가 서로 다르다 — 경로로 재면 옛 항목이 그대로 남아
#   이중 발화(또는 지워진 디렉터리를 가리키는 죽은 훅)가 된다. 다른 체크아웃에서 병합한
#   항목도 같은 이유로 걸려야 한다. 이름이 «닮기만 한» 남의 훅(reply-gate-custom.sh 등)은
#   뒤따르는 문자를 따옴표·공백·끝으로 한정해 걸리지 않는다.
_stale_re() {
  _n=""
  for _h in $REQUIRED_HOOKS; do
    _e="$(printf '%s' "$_h" | command sed 's/\./\\./g')"
    _n="${_n}${_n:+|}${_e}"
  done
  printf '[/\\\\]hooks[/\\\\](%s)(["'"'"' ]|$)' "$_n"
}

# 이름이 같다고 «우리 것» 은 아니다 — 소유 표식이 하나라도 있어야 지운다.
#   이름만 보는 자는 남의 살아있는 훅(예: ~/x/hooks/rule-router.sh)을 지우고,
#   --verify 를 거짓 실패로 만든다. 그래서 이름 자(정규식) 뒤에 소유 자를 한 번 더 댄다.
#   ⓐ 명령이 우리 래퍼를 거친다 · ⓑ 명령에 thiscode(대소문자 무시) 가 있다
#   ⓒ 그 훅의 형제로 우리 plugin.json 이 실재한다 · ⓓ 가리키는 파일이 «아예 없다»(죽은 항목)
#   ⓓ 는 경로에 변수($HOME 등)가 있으면 판정하지 않는다 — 전개 안 한 문자열은 항상 «없다» 로 보인다.
_owned_by_us() {
  case "$1" in
    *hooks/lib/bot-only.sh*) return 0 ;;
  esac
  case "$(printf '%s' "$1" | command sed 'y/ABCDEFGHIJKLMNOPQRSTUVWXYZ/abcdefghijklmnopqrstuvwxyz/')" in
    *thiscode*) return 0 ;;
  esac
  _p="$(_path_of "$1")"
  [ -n "$_p" ] || return 1
  _sib="$(dirname "$_p")/../.claude-plugin/plugin.json"
  if [ -f "$_sib" ] && command grep -q '"name"[[:space:]]*:[[:space:]]*"thiscode"' "$_sib" 2>/dev/null; then
    return 0
  fi
  case "$_p" in
    *'$'*) return 1 ;;
  esac
  [ -e "$_p" ] || return 0
  return 1
}

# 이름 자에 걸린 «후보» 만 뽑는다(소유 판정은 셸에서 한 번만 — 양 엔진이 같은 규칙을 쓰도록).
#   출력 = EV<TAB>command · 명령 안 개행은 \n 리터럴로 바꿔 «1 항목 = 1 줄» 을 보장한다.
_stale_candidates() {
  [ -f "$1" ] || return 0
  case "$(_engine)" in
    jq)
      jq -r --arg re "$(_stale_re)" '(.hooks // {}) | to_entries[] | .key as $e | .value[]? | .hooks[]? | select((.command // "") | test($re)) | "\($e)\t\((.command // "") | gsub("\n"; "\\n"))"' "$1" 2>/dev/null
      ;;
    node)
      node -e 'const fs=require("fs");const re=new RegExp(process.argv[2]);let j={};try{j=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));}catch(e){process.exit(0);}for(const ev of Object.keys(j.hooks||{}))for(const g of j.hooks[ev]||[])for(const h of g.hooks||[])if(re.test(h.command||""))console.log(ev+"\t"+String(h.command).replace(/\n/g,"\\n"));' "$1" "$(_stale_re)" 2>/dev/null
      ;;
    *) return 0 ;;
  esac
}

_TAB="$(printf '\t')"

# 지울 것 = 후보 중 «우리 것»
_stale_list() {
  _stale_candidates "$1" | while IFS= read -r _line; do
    _owned_by_us "${_line#*"$_TAB"}" && printf '%s\n' "$_line"
  done
}

# 손대지 않을 것 = 후보 중 소유가 «불명» 인 것(이름만 같은 남의 훅이 여기 온다)
_ambiguous_list() {
  _stale_candidates "$1" | while IFS= read -r _line; do
    _owned_by_us "${_line#*"$_TAB"}" || printf '%s\n' "$_line"
  done
}

# 건수는 «줄 수» 로 센다 — grep 이 없는 환경에서 0 으로 조용히 통과하지 않도록 엔진 밖 계수기를 쓴다.
_stale_count() { _stale_list "$1" | awk 'END{print NR}'; }
_ambiguous_count() { _ambiguous_list "$1" | awk 'END{print NR}'; }

# 소유 불명 항목은 지우지 않고 «보여만» 준다(계수에도 넣지 않는다 — 거짓 실패가 되면 안 된다).
_warn_ambiguous() {
  _amb="$(_ambiguous_count "$1")"
  [ "$_amb" -gt 0 ] 2>/dev/null || return 0
  echo "주의 — 이름은 같지만 소유가 불명한 항목 $_amb 건은 손대지 않았다(손으로 검토):"
  _ambiguous_list "$1" | command sed 's/^/  - /'
}

# 잔존 제거본을 <출력파일> 에 쓴다. 지울 대상은 «$3 = _stale_list 가 낸 목록» 그것뿐이다
# (엔진이 정규식으로 다시 고르면 소유 판정을 건너뛴 채 남의 훅을 지운다).
# 빈 그룹·빈 이벤트는 같이 치운다(껍데기가 남으면 「등록돼 있다」로 오독된다).
# 규칙은 jq·node 두 경로가 «같다».
_strip_stale() {
  case "$(_engine)" in
    jq)
      jq --arg kill "$3" '($kill | split("\n") | map(select(length > 0))) as $K
| .hooks = ((.hooks // {}) | with_entries(.key as $e | .value = ((.value // []) | map(.hooks = ((.hooks // []) | map(select((($e + "\t" + ((.command // "") | gsub("\n"; "\\n"))) as $sig | ($K | index($sig)) == null))))) | map(select((.hooks | length) > 0)))) | with_entries(select((.value | length) > 0)))' "$1" > "$2" 2>/dev/null
      ;;
    node)
      node -e 'const fs=require("fs");const kill=new Set(String(process.argv[3]).split("\n").filter((x)=>x.length));let j;try{j=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));}catch(e){process.exit(1);}const src=j.hooks||{};const out={};for(const ev of Object.keys(src)){const groups=[];for(const g of src[ev]||[]){const kept=(g.hooks||[]).filter((h)=>!kill.has(ev+"\t"+String(h.command||"").replace(/\n/g,"\\n")));if(kept.length)groups.push(Object.assign({},g,{hooks:kept}));}if(groups.length)out[ev]=groups;}j.hooks=out;fs.writeFileSync(process.argv[2],JSON.stringify(j,null,2));' "$1" "$2" "$3"
      ;;
    *) return 1 ;;
  esac
}

# 명령들($1, 줄바꿈 구분) 중 «래퍼를 앞세운» 명령 안에 그 훅 이름($2)이 있나.
#   이름만 어딘가 있으면 통과시키면, 래퍼를 우회한 등록이 「래퍼 경유」로 보고된다.
_WRAPPER_PREFIX='bash "${CLAUDE_PLUGIN_ROOT}/hooks/lib/bot-only.sh" '
_wrapped_has() {
  _hit=1
  _oi="$IFS"; IFS='
'
  for _c in $1; do
    case "$_c" in
      "$_WRAPPER_PREFIX"*)
        case "$_c" in *"$2"*) _hit=0 ;; esac
        ;;
    esac
  done
  IFS="$_oi"
  return $_hit
}

# settings.json 의 enabledPlugins 에 thiscode 가 켜져 있는가(마켓 설치 축).
# 개발 체크아웃(--plugin-dir)은 여기 안 잡힌다 — 그래서 «실패» 가 아니라 «경고» 로 쓴다.
_plugin_enabled() {
  [ -f "$1" ] || return 1
  case "$(_engine)" in
    jq)   jq -e '[(.enabledPlugins // {}) | to_entries[] | select((.key | startswith("thiscode@")) and (.value == true))] | length > 0' "$1" >/dev/null 2>&1 ;;
    node) node -e 'const fs=require("fs");let j={};try{j=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));}catch(e){process.exit(1);}const e=j.enabledPlugins||{};process.exit(Object.keys(e).some((k)=>k.indexOf("thiscode@")===0&&e[k]===true)?0:1);' "$1" >/dev/null 2>&1 ;;
    *) return 1 ;;
  esac
}

# ── --verify (플러그인 모드): hooks.json 이 «완비» 됐나 ─────────────
# 자는 「등록 파일 완비」까지다. Claude Code 가 실제로 로드했는지는 이 층에서 관측할 수
# 없다 — 그건 새 세션을 한 번 띄워 보는 수동 축이다.
if [ "$VERIFY" -eq 1 ] && [ "$PLUGIN_MODE" -eq 1 ]; then
  if [ "$(_engine)" = "none" ]; then
    echo "install-hooks: jq 도 node 도 없어 hooks.json 을 읽을 수 없다 — 둘 중 하나를 설치할 것" >&2
    exit 2
  fi
  missing=0
  # ① 파싱
  if ! _json_ok "$HOOKS_JSON"; then
    echo "빠짐 — hooks.json 을 JSON 으로 읽을 수 없다: $HOOKS_JSON"
    echo "검사 실패 — 빠진 항목 1 건."
    exit 1
  fi
  cmds="$(_list_commands "$HOOKS_JSON")"
  # ② 4 이벤트에 각각 훅이 하나 이상
  for ev in SessionStart UserPromptSubmit PreToolUse Stop; do
    if ! _event_present "$HOOKS_JSON" "$ev"; then
      echo "빠짐 — hooks.json 의 이벤트에 등록된 훅이 없다: $ev"
      missing=$((missing + 1))
    fi
  done
  # ③ 필수 훅 전부 — «래퍼를 앞세운» 명령 안에 있어야 한다.
  #    이름이 어딘가 있기만 하면 통과시키면, 래퍼를 우회한 등록도 「래퍼 경유」로 보고된다.
  for want in $REQUIRED_HOOKS; do
    if ! _wrapped_has "$cmds" "$want"; then
      echo "빠짐 — hooks.json 에 훅이 래퍼 경유로 등록돼 있지 않다: $want"
      missing=$((missing + 1))
    fi
  done
  # ③′ 래퍼를 «거치지 않는» 명령 — 그 훅은 일반 세션에서도 돈다
  bare=0
  bare_first=""
  oldifs="$IFS"; IFS='
'
  for c in $cmds; do
    [ -z "$c" ] && continue
    case "$c" in
      *"hooks/lib/bot-only.sh"*) ;;
      *)
        bare=$((bare + 1))
        [ -n "$bare_first" ] || bare_first="$c"
        ;;
    esac
  done
  IFS="$oldifs"
  if [ "$bare" -gt 0 ]; then
    echo "빠짐 — 래퍼를 거치지 않는 명령 $bare 건: $bare_first"
    missing=$((missing + bare))
  fi
  # ④ ${CLAUDE_PLUGIN_ROOT} 를 실제 플러그인 경로로 바꿔 파일 실재 확인.
  #    등록만 되고 파일이 없으면 «조용한 무반응» 이 된다 — 병합 모드와 같은 축이다.
  paths="$(printf '%s\n' "$cmds" | command grep -o '\${CLAUDE_PLUGIN_ROOT}/[A-Za-z0-9._/-]*' | sort -u)"
  oldifs="$IFS"; IFS='
'
  for rel in $paths; do
    [ -z "$rel" ] && continue
    p="$PLUGIN_DIR${rel#'${CLAUDE_PLUGIN_ROOT}'}"
    if [ ! -f "$p" ]; then
      echo "빠짐 — hooks.json 이 가리키는 파일이 실재하지 않는다: $p"
      missing=$((missing + 1))
    fi
  done
  IFS="$oldifs"
  # ⑤ 봇 세션 래퍼 — 이게 없으면 훅이 «모든» 세션에서 돈다
  if [ ! -f "$BOT_ONLY" ]; then
    echo "빠짐 — 봇 세션 래퍼가 실재하지 않는다: $BOT_ONLY"
    missing=$((missing + 1))
  fi
  # ⑥ 옛 병합 잔존 = 같은 훅이 두 번 발화한다.
  #    파싱 실패를 «잔존 0» 으로 읽지 않는다 — 못 읽은 것과 없는 것은 다르다.
  if [ -f "$SETTINGS" ] && [ ! -s "$SETTINGS" ]; then
    echo "주의 — settings.json 이 비어 있다: $SETTINGS"
  elif [ -f "$SETTINGS" ] && ! _json_ok "$SETTINGS"; then
    echo "install-hooks: $SETTINGS 를 JSON 으로 읽을 수 없다 — 손으로 고칠 것"
    missing=$((missing + 1))
  else
    stale="$(_stale_count "$SETTINGS")"
    if [ "$stale" -gt 0 ] 2>/dev/null; then
      echo "빠짐 — 옛 병합 항목 $stale 건 잔존(이중 발화): $SETTINGS"
      echo "  지우려면: bash scripts/install-hooks.sh --home \"$HOME_DIR\""
      missing=$((missing + 1))
    fi
    # 소유 불명 동명 항목은 «경고만» — 계수에 넣으면 남의 훅 때문에 검사가 거짓 실패한다.
    _warn_ambiguous "$SETTINGS"
  fi
  # ⑦ 플러그인 활성 — 경고만 낸다(개발 체크아웃을 거짓 실패로 만들지 않는다)
  if _plugin_enabled "$SETTINGS"; then
    echo "등록 확인 — enabledPlugins 에 thiscode 가 켜져 있다 ($SETTINGS)"
  else
    echo "미확인 — enabledPlugins 에 thiscode 없음: 마켓 설치면 /plugin 에서 켤 것, 개발 체크아웃(--plugin-dir)이면 정상"
  fi
  if [ "$missing" -gt 0 ]; then
    echo "검사 실패 — 빠진 항목 $missing 건. hooks.json: $HOOKS_JSON"
    exit 1
  fi
  echo "검사 통과 — 플러그인 모드: 4 이벤트 + 필수 훅 전부 + 래퍼 경유 + 명령 파일 실재 ($HOOKS_JSON)"
  exit 0
fi

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

# ── 플러그인 모드 기본 실행: 병합 대신 «옛 병합 잔존 정리» ──────────
# 플러그인이 훅을 직접 싣는 상태에서 settings.json 에도 같은 훅이 남아 있으면 한 번
# 일어난 일에 훅이 두 번 발화한다. 그 중복만 지우고, 병합은 하지 않는다.
if [ "$PLUGIN_MODE" -eq 1 ]; then
  stale=0
  if [ -f "$SETTINGS" ]; then
    if [ "$(_engine)" = "none" ]; then
      echo "install-hooks: jq 도 node 도 없어 $SETTINGS 를 읽을 수 없다 — 둘 중 하나를 설치할 것" >&2
      exit 2
    fi
    # 0 바이트는 «없음» 과 같이 본다. 깨진 JSON 은 못 읽은 것이지 «잔존 0» 이 아니다 —
    # 그 상태에서 손대면 사용자가 못 되돌린다. 그래서 한 글자도 건드리지 않고 멈춘다.
    if [ ! -s "$SETTINGS" ]; then
      echo "주의 — settings.json 이 비어 있다: $SETTINGS"
    elif ! _json_ok "$SETTINGS"; then
      echo "install-hooks: $SETTINGS 를 JSON 으로 읽을 수 없다 — 손으로 고칠 것" >&2
      exit 2
    else
      stale="$(_stale_count "$SETTINGS")"
    fi
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[미리보기] 플러그인이 훅을 직접 싣는다 — 병합하지 않는다 ($HOOKS_JSON)"
    if [ "$stale" -gt 0 ] 2>/dev/null; then
      echo "[미리보기] 지울 옛 병합 항목 $stale 건:"
      _stale_list "$SETTINGS" | command sed 's/^/  - /'
    else
      echo "[미리보기] 지울 옛 병합 항목 없음."
    fi
    _warn_ambiguous "$SETTINGS"
    echo "[미리보기] 파일은 바꾸지 않았다."
    exit 0
  fi

  if [ "$stale" -gt 0 ] 2>/dev/null; then
    BACKUP="$SETTINGS.bak-$(date +%s)"
    cp "$SETTINGS" "$BACKUP" 2>/dev/null || true
    KILL="$(_stale_list "$SETTINGS")"
    # 제자리 쓰기 — mv 로 갈아치우면 권한이 넓어지고(600→644) 심링크가 일반 파일로 바뀐다.
    if _strip_stale "$SETTINGS" "$SETTINGS.tmp" "$KILL" && cat "$SETTINGS.tmp" > "$SETTINGS"; then
      rm -f "$SETTINGS.tmp"
      echo "옛 병합 항목 $stale 건 제거 — $SETTINGS (백업 $BACKUP · 이중 발화 차단)"
    else
      rm -f "$SETTINGS.tmp"
      echo "install-hooks: 옛 병합 항목을 지우지 못했다 — $SETTINGS 는 손대지 않았다" >&2
      exit 2
    fi
  fi

  _warn_ambiguous "$SETTINGS"
  echo "플러그인이 훅을 직접 싣는다 — settings.json 병합은 하지 않는다 ($HOOKS_JSON · 봇 세션에서만 동작)"
  echo "검사하려면: bash scripts/install-hooks.sh --verify --home \"$HOME_DIR\""
  exit 0
fi

# ── 병합 ────────────────────────────────────────────────────────────
ENGINE="$(_engine)"
if [ "$ENGINE" = "none" ]; then
  echo "install-hooks: 병합에는 jq 또는 node 가 필요한데 둘 다 없다." >&2
  echo "  jq(macOS: brew install jq · Debian: apt-get install jq) 또는 Node.js 를 설치한 뒤 다시 실행할 것." >&2
  exit 2
fi

# 경로를 JSON 문자열 안에 넣는다 — Windows(Git Bash) 에서 --plugin-dir 로 «백슬래시 경로»가
#   오면 \ 가 JSON 이스케이프로 읽혀 jq·node 둘 다 parse error 를 낸다(CI windows-latest 실증).
#   백슬래시와 큰따옴표만 이스케이프한다(경로에 올 수 있는 두 글자).
PLUGIN_DIR_JSON="$(printf '%s' "$PLUGIN_DIR" | command sed 's/\\/\\\\/g; s/"/\\"/g')"
PATCH=$(cat <<EOF
{
  "hooks": {
    "SessionStart": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "bash '$PLUGIN_DIR_JSON/hooks/bot-session-init.sh'", "timeout": 10 }
      ] }
    ],
    "UserPromptSubmit": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "bash '$PLUGIN_DIR_JSON/hooks/discord-slash-cmd.sh'", "timeout": 5 },
        { "type": "command", "command": "bash '$PLUGIN_DIR_JSON/hooks/regression-self-check.sh'", "timeout": 3 },
        { "type": "command", "command": "bash '$PLUGIN_DIR_JSON/hooks/rule-router.sh'", "timeout": 3 }
      ] }
    ],
    "PreToolUse": [
      { "matcher": "mcp__plugin_discord_discord__reply|mcp__plugin_discord_discord__edit_message", "hooks": [
        { "type": "command", "command": "python3 '$PLUGIN_DIR_JSON/hooks/dispatch-room-gate.py'", "timeout": 5 }
      ] }
    ],
    "Stop": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "bash '$PLUGIN_DIR_JSON/hooks/meeting-stop-reread.sh'", "timeout": 5 },
        { "type": "command", "command": "bash '$PLUGIN_DIR_JSON/hooks/reply-gate.sh'", "timeout": 5 }
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

# 제자리 쓰기 — mv 는 권한을 넓히고(600→644) 심링크를 일반 파일로 갈아치운다.
cat "$SETTINGS.tmp" > "$SETTINGS" && rm -f "$SETTINGS.tmp"
echo "훅 병합 완료 — $SETTINGS (엔진 $ENGINE · 백업 $BACKUP)"
echo "검사하려면: bash scripts/install-hooks.sh --verify --home \"$HOME_DIR\""
