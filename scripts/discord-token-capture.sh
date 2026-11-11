#!/usr/bin/env bash
# discord-token-capture.sh — Discord 봇 토큰을 «대화를 거치지 않고» 봇 폴더의 .env 에 저장한다.
#
# 토큰이 가는 길은 둘뿐이다. 어느 쪽도 값이 명령 글자 · 도구 인자 · 대화 글에 들어가지 않는다.
#   ① 클립보드 길(에이전트가 실행):
#        bash scripts/discord-token-capture.sh arm
#          클립보드에 표식을 심는다(«복사가 안 됐는데 옛 내용을 토큰으로 착각» 을 잡으려는 것).
#        (포털의 «복사» 버튼을 누른다 — 에이전트가, 안 되면 사용자가)
#        bash scripts/discord-token-capture.sh capture <봇이름>
#          클립보드 → 표식 대조 → 꼴 검사 → 0600 .env → 클립보드 비움. 값은 출력하지 않는다.
#   ② 사람 길(사용자가 «자기 터미널» 에서 직접 실행 — 클립보드 도구가 없거나 ①이 안 될 때):
#        bash scripts/discord-token-capture.sh paste <봇이름>
#          물음에 토큰을 붙여 넣는다(화면에 안 보인다). 터미널이 아니면 거부한다 —
#          에이전트의 셸에는 터미널이 없으므로 에이전트는 이 길을 대신 실행할 수 없다.
#
# 클립보드 도구: macOS = pbcopy/pbpaste · WSL = clip.exe / powershell.exe Get-Clipboard ·
#   Linux = wl-copy/wl-paste(Wayland) → xclip. 도구가 없으면 exit 4 로 멈추고 ②를 안내한다.
#   토큰을 대화로 받는 길로는 떨어지지 않는다.
#
# exit: 0 저장됨 · 1 복사 안 됨/꼴 아님/여러 줄 · 2 쓰는 법 틀림 · 3 .env 를 안전하게 못 씀 · 4 클립보드 도구 없음
# 마지막 줄에 install-gate.sh 에 넘길 사유 코드를 «사유 코드: <코드>» 로 알려 준다.
set +x   # 추적 출력이 켜져 있어도 값이 찍히지 않게
set -u

MARKER='THISCODE_NOT_COPIED_YET'
MODE="${1:-}"
BOT="${2:-}"
BOT_SHOWN=''

usage() {
  echo "쓰는 법: discord-token-capture.sh arm | capture <봇이름> | paste <봇이름>" >&2
  exit 2
}

bot_dir() {   # 봇 이름은 값 전체가 영문 · 숫자 · - · _ 여야 한다(경로 조각이 못 들어오게)
  local LC_ALL=C
  case "$BOT" in
    ''|*[!A-Za-z0-9_-]*) usage ;;
  esac
  BOT_SHOWN="$BOT"   # 꼴 검사를 지난 이름만 안내 글에 찍는다
  BOT_DIR="$HOME/.claude/channels/discord-$BOT"
  ENV_FILE="$BOT_DIR/.env"
}

is_wsl() {
  case "$(uname -r 2>/dev/null)" in
    *[Mm]icrosoft*) return 0 ;;
  esac
  [ -r /proc/version ] && command grep -qi microsoft /proc/version 2>/dev/null
}

have() { command -v "$1" >/dev/null 2>&1; }

no_tool() {   # $1 = 설치 안내 한 줄
  echo "❌ 클립보드 도구가 없어 여기서 멈춥니다 — $1" >&2
  echo "   또는 터미널 새 창에서 직접: bash $0 paste ${BOT_SHOWN:-<봇이름>}   (물음에 토큰을 붙여 넣습니다 · 화면에 안 보입니다)" >&2
  echo "   토큰을 대화 창에 붙여 넣지 마세요." >&2
  echo "사유 코드: tool-error" >&2
  exit 4
}

pick_clipboard() {
  case "$(uname -s 2>/dev/null)" in
    Darwin)
      have pbcopy && have pbpaste || no_tool "pbcopy/pbpaste 를 찾지 못했습니다"
      clip_write() { pbcopy; }
      clip_read()  { pbpaste; }
      clip_clear() { printf '' | pbcopy; } ;;
    *)
      if is_wsl; then
        have clip.exe && have powershell.exe || no_tool "WSL 에서 clip.exe / powershell.exe 를 찾지 못했습니다(윈도우 경로가 PATH 에 있는지 확인)"
        clip_write() { clip.exe; }
        clip_read()  { powershell.exe -NoProfile -Command Get-Clipboard; }
        clip_clear() { printf '' | clip.exe; }
      elif [ -n "${WAYLAND_DISPLAY:-}" ] && have wl-copy && have wl-paste; then
        clip_write() { wl-copy; }
        clip_read()  { wl-paste --no-newline; }
        clip_clear() { wl-copy --clear; }
      elif have xclip; then
        clip_write() { xclip -selection clipboard; }
        clip_read()  { xclip -selection clipboard -o; }
        clip_clear() { printf '' | xclip -selection clipboard; }
      else
        no_tool "설치: sudo apt install xclip (Wayland 면 wl-clipboard · Fedora: sudo dnf install xclip)"
      fi ;;
  esac
}

# 값 검사 — 결과만 말한다. 값은 어디에도 찍지 않는다.
check_value() {   # 전역 V 를 다듬고 검사한다
  local LC_ALL=C
  V="${V%$'\r'}"
  case "$V" in
    *$'\n'*|*$'\r'*)
      echo "❌ 여러 줄이 들어왔습니다 — 토큰 한 줄만 다시 복사해 주세요(저장하지 않았습니다)." >&2
      echo "사유 코드: format-mismatch" >&2
      return 1 ;;
  esac
  V="${V#"${V%%[![:space:]]*}"}"
  V="${V%"${V##*[![:space:]]}"}"
  if [ -z "$V" ] || [ "$V" = "$MARKER" ]; then
    echo "❌ 복사된 값이 없습니다 — 포털의 «복사» 버튼이 눌리지 않았습니다(저장하지 않았습니다)." >&2
    echo "사유 코드: clipboard-empty" >&2
    return 1
  fi
  if ! [[ "$V" =~ ^[A-Za-z0-9_.-]{50,120}$ ]]; then
    echo "❌ 토큰 꼴이 아닙니다(영문 · 숫자 · . _ - 로 50~120자) — 다른 것이 복사됐을 수 있습니다(저장하지 않았습니다)." >&2
    echo "사유 코드: format-mismatch" >&2
    return 1
  fi
  return 0
}

# .env 는 본인만 읽는다. 다른 키는 그대로 두고 DISCORD_BOT_TOKEN 줄만 바꾼다.
save_value() {
  local tmp
  umask 077
  if [ -L "$BOT_DIR" ] || [ -L "$ENV_FILE" ]; then
    echo "❌ 봇 폴더나 .env 가 심볼릭 링크라 쓰지 않습니다 — $BOT_DIR" >&2; return 3
  fi
  mkdir -p "$BOT_DIR" 2>/dev/null && [ -d "$BOT_DIR" ] && [ -O "$BOT_DIR" ] || {
    echo "❌ 봇 폴더를 쓸 수 없습니다 — $BOT_DIR" >&2; return 3; }
  if [ -e "$ENV_FILE" ] && { [ ! -f "$ENV_FILE" ] || [ ! -O "$ENV_FILE" ]; }; then
    echo "❌ .env 가 일반 파일이 아니거나 내 파일이 아니라 쓰지 않습니다 — $ENV_FILE" >&2; return 3
  fi
  tmp="$(mktemp "$BOT_DIR/.env.XXXXXX")" || { echo "❌ 임시 파일을 못 만들었습니다 — $BOT_DIR" >&2; return 3; }
  chmod 600 "$tmp" 2>/dev/null || true
  if [ -f "$ENV_FILE" ]; then
    command grep -v '^DISCORD_BOT_TOKEN=' "$ENV_FILE" > "$tmp" 2>/dev/null || true
  fi
  printf 'DISCORD_BOT_TOKEN=%s\n' "$V" >> "$tmp" || { rm -f "$tmp"; echo "❌ 저장하지 못했습니다" >&2; return 3; }
  mv -f "$tmp" "$ENV_FILE" || { rm -f "$tmp"; echo "❌ 저장하지 못했습니다" >&2; return 3; }
  chmod 600 "$ENV_FILE" 2>/dev/null || true   # 윈도우에서는 뜻이 없다
  if [ -L "$ENV_FILE" ] || [ ! -f "$ENV_FILE" ]; then
    echo "❌ 저장한 뒤 .env 가 바뀌었습니다 — $ENV_FILE" >&2; return 3
  fi
  echo "✅ 토큰 저장 — 길이 ${#V}자 (값은 출력하지 않습니다) · $ENV_FILE"
  return 0
}

case "$MODE" in
  arm)
    pick_clipboard
    printf '%s' "$MARKER" | clip_write || { echo "❌ 클립보드에 쓰지 못했습니다" >&2; echo "사유 코드: tool-error" >&2; exit 4; }
    echo "🔒 준비됨 — 이제 포털의 «복사» 버튼을 누릅니다. 눌리기 전까지 클립보드에는 표식만 있습니다."
    ;;
  capture)
    bot_dir
    pick_clipboard
    V="$(clip_read 2>/dev/null)" || { echo "❌ 클립보드를 읽지 못했습니다" >&2; echo "사유 코드: tool-error" >&2; exit 4; }
    if ! check_value; then
      # 표식이 아닌 무언가가 복사돼 있었다면(토큰이 섞였을 수 있다) 클립보드에 남기지 않는다.
      if [ -n "$V" ] && [ "$V" != "$MARKER" ]; then clip_clear >/dev/null 2>&1 || true; fi
      V=''
      exit 1
    fi
    save_value; rc=$?
    V=''
    [ "$rc" -eq 0 ] || exit "$rc"
    clip_clear >/dev/null 2>&1 || echo "⚠️ 클립보드를 비우지 못했습니다 — 다른 것을 한 번 복사해 덮어 주세요." >&2
    ;;
  paste)
    bot_dir
    if [ ! -t 0 ]; then
      echo "❌ 이 길은 사용자가 «자기 터미널» 에서 직접 실행해야 합니다(여기에는 터미널이 없습니다)." >&2
      echo "   터미널 새 창에서: bash $0 paste $BOT" >&2
      exit 2
    fi
    # 물음을 보이기 «전에» 화면 되비침을 끈다 — 물음이 뜨자마자 붙여 넣어도 값이 화면에 찍히지 않게.
    TTY_WAS="$(stty -g 2>/dev/null || true)"
    trap '[ -n "$TTY_WAS" ] && stty "$TTY_WAS" 2>/dev/null' EXIT
    stty -echo 2>/dev/null || true
    printf '토큰을 붙여 넣고 Enter (화면에 안 보입니다): ' >&2
    IFS= read -rs V || V=''
    [ -n "$TTY_WAS" ] && stty "$TTY_WAS" 2>/dev/null
    printf '\n' >&2
    check_value || exit 1
    save_value; rc=$?
    V=''
    exit "$rc"
    ;;
  *) usage ;;
esac
