#!/usr/bin/env bash
# discord-token-capture.sh — Discord 봇 토큰을 «대화를 거치지 않고» 봇 폴더의 .env 에 저장한다.
#
# 토큰이 가는 길은 둘뿐이다. 어느 쪽도 값이 명령 글자 · 도구 인자 · 대화 글에 들어가지 않는다.
#   ① 클립보드 길(에이전트가 실행):
#        bash scripts/discord-token-capture.sh arm <봇이름>
#          일회용 값을 새로 만들어 클립보드에 «표식+그 값» 을 심고, 같은 값 · 봇 이름 · 시각을
#          본인만 읽는 일회용 상태 파일에 적는다. 값은 출력하지 않는다.
#        (포털의 «복사» 버튼을 누른다 — 에이전트가, 안 되면 사용자가)
#        bash scripts/discord-token-capture.sh capture <봇이름>
#          같은 봇으로 방금(ARM_TTL_MIN 분 안에) arm 한 기록이 있을 때만 클립보드를 읽는다.
#          표식 대조 → 꼴 검사 → 0600 .env → 클립보드 비움. 값은 출력하지 않는다.
#          arm 기록은 한 번 쓰면 지운다 — arm 없이, 다른 봇의 arm 으로, 시간이 지나서, 두 번째로
#          부르면 클립보드를 읽지도 않고 거부한다(옛 토큰이 클립보드에 남아 있어도 저장되지 않는다).
#   ② 사람 길(사용자가 «자기 터미널» 에서 직접 실행 — 클립보드 도구가 없거나 ①이 안 될 때):
#        bash scripts/discord-token-capture.sh paste <봇이름>
#          물음에 토큰을 붙여 넣는다(화면에 안 보인다). 표준입력이 터미널이 아니면 거부한다.
#          이 검사는 «실수로 파이프로 부르는 것» 을 막을 뿐이다. 같은 사용자 권한으로 도는 프로그램은
#          가짜 터미널을 만들 수 있으므로, 이것은 에이전트를 막는 권한 경계가 아니다 — 사용자가
#          토큰을 자기 터미널에만 넣는다는 운영 절차다.
#
# 클립보드 도구: macOS = pbcopy/pbpaste · WSL = clip.exe / powershell.exe Get-Clipboard ·
#   Linux = wl-copy/wl-paste(Wayland) → xclip. 도구가 없으면 exit 4 로 멈추고 ②를 안내한다.
#   토큰을 대화로 받는 길로는 떨어지지 않는다.
#
# 본인만 읽게: 봇 폴더 0700 · .env 0600. macOS 에서는 파일 ACL(상속 ACL 포함)도 지우고 다시 확인한다 —
#   권한이 600 이어도 ACL 이 남으면 남이 읽을 수 있기 때문이다. 못 지우면 저장하지 않는다.
#   Linux · Windows 의 ACL 은 보지 않는다.
#
# exit: 0 저장됨(클립보드도 비움) · 1 복사 안 됨/꼴 아님/여러 줄/arm 기록 없음·지남 · 2 쓰는 법 틀림 ·
#       3 파일을 안전하게 못 씀 · 4 클립보드 도구 없음 · 5 저장은 됐지만 클립보드를 못 비움
# 실패하면 마지막 줄에 install-gate.sh 에 넘길 사유 코드를 «사유 코드: <코드>» 로 알려 준다.
set +x   # 추적 출력이 켜져 있어도 값이 찍히지 않게
set -u

MARKER='THISCODE_NOT_COPIED_YET'
# arm 뒤 capture 까지 기다려 주는 시간(분). 그 사이 사람이 비밀번호 · 인증 코드 창을 지나야 할 수 있어
# 몇 초로는 모자라고, 길수록 옛 클립보드 값이 섞일 틈이 커진다. 문서(create-bot Step 4)와 같은 숫자.
ARM_TTL_MIN=10
MODE="${1:-}"
BOT="${2:-}"
BOT_SHOWN=''
ARM_WHY=''

usage() {
  echo "쓰는 법: discord-token-capture.sh arm <봇이름> | capture <봇이름> | paste <봇이름>" >&2
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
  ARM_DIR="$HOME/.thiscode/token-arm"
  ARM_FILE="$ARM_DIR/$BOT.arm"
}

is_wsl() {
  case "$(uname -r 2>/dev/null)" in
    *[Mm]icrosoft*) return 0 ;;
  esac
  [ -r /proc/version ] && command grep -qi microsoft /proc/version 2>/dev/null
}

is_darwin() { case "${OSTYPE:-}" in darwin*) return 0 ;; esac; return 1; }   # bash 가 아는 값(PATH 의 uname 이 아님)

modes_meaningful() {   # 윈도우 git-bash 는 권한 비트가 뜻이 없다
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*) return 1 ;;
  esac
  return 0
}

have() { command -v "$1" >/dev/null 2>&1; }

stat_mode_links() {   # "<8진 권한> <하드 링크 수>" — GNU stat 먼저, 아니면 BSD stat
  command stat -c '%a %h' "$1" 2>/dev/null || command stat -f '%Lp %l' "$1" 2>/dev/null
}

# macOS: 파일 ACL 을 지우고, 지워졌는지 다시 본다(ACL 이 있으면 `ls -le` 가 둘째 줄부터 그것을 찍는다).
# 다른 OS 에서는 아무것도 하지 않는다.
acl_clear() {   # $1 = 파일이나 폴더
  is_darwin || return 0
  chmod -N "$1" 2>/dev/null || return 1
  [ "$(LC_ALL=C ls -lde "$1" 2>/dev/null | wc -l | tr -d ' ')" = "1" ]
}

# 본인만 쓰는 폴더: 심볼릭 링크가 아닌 진짜 폴더 · 내 것 · 0700 · (macOS) ACL 없음
private_dir() {   # $1 = 폴더(없으면 만든다)
  local info
  [ -L "$1" ] && return 1
  if [ ! -e "$1" ]; then
    ( umask 077; mkdir -p "$1" ) 2>/dev/null || return 1
  fi
  [ -L "$1" ] && return 1
  [ -d "$1" ] && [ -O "$1" ] || return 1
  modes_meaningful || return 0
  chmod 700 "$1" 2>/dev/null || return 1
  acl_clear "$1" || return 1
  info="$(stat_mode_links "$1")" || return 1
  [ "${info%% *}" = "700" ]
}

# 본인만 읽는 파일: 심볼릭 링크 아님 · 일반 파일 · 내 것 · 하드 링크 1 · 0600 · (macOS) ACL 없음
private_file() {   # $1 = 이미 있는 파일
  local info
  [ -L "$1" ] && return 1
  [ -f "$1" ] && [ -O "$1" ] || return 1
  modes_meaningful || return 0
  chmod 600 "$1" 2>/dev/null || return 1
  acl_clear "$1" || return 1
  info="$(stat_mode_links "$1")" || return 1
  [ "$info" = "600 1" ]
}

# ── 읽는 길용: «확인만» 한다(아무것도 고치지 않는다) ──────────────────
# 위의 private_dir · private_file 은 권한과 ACL 을 «고친 뒤» 참을 돌려준다 — 새로 쓰는 길에만 쓴다.
# 이미 있는 것을 읽어서 믿을 때 그것을 쓰면, 고치기 전에 남이 넣어 둔 것을 받아들이게 된다.
acl_none() {   # $1 = 파일이나 폴더 — macOS 에서 ACL 줄이 없는가(다른 OS 는 보지 않는다)
  is_darwin || return 0
  [ "$(LC_ALL=C ls -lde "$1" 2>/dev/null | wc -l | tr -d ' ')" = "1" ]
}

dir_is_private() {   # $1 = 폴더 — 링크가 아닌 진짜 폴더 · 내 것 · 정확히 0700 · (macOS) ACL 없음
  local info
  [ -L "$1" ] && return 1
  [ -d "$1" ] && [ -O "$1" ] || return 1
  modes_meaningful || return 0
  info="$(stat_mode_links "$1")" || return 1
  [ "${info%% *}" = "700" ] || return 1
  acl_none "$1"
}

file_is_private() {   # $1 = 파일 — 링크 아님 · 일반 파일 · 내 것 · 정확히 0600 · 하드 링크 1 · (macOS) ACL 없음
  local info
  [ -L "$1" ] && return 1
  [ -f "$1" ] && [ -O "$1" ] || return 1
  modes_meaningful || return 0
  info="$(stat_mode_links "$1")" || return 1
  [ "$info" = "600 1" ] || return 1
  acl_none "$1"
}

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

# ── arm 기록(일회용) ────────────────────────────────────────────────
not_armed() {   # $1 = 까닭 한 줄 — 클립보드는 읽지 않았다
  echo "❌ $1 — 클립보드를 읽지 않았습니다. 먼저: bash $0 arm $BOT_SHOWN  → 포털의 «복사» 버튼 → capture" >&2
  echo "사유 코드: not-armed" >&2
  exit 1
}

arm_write() {   # 새 일회용 값을 만들어 ARM_NONCE 에 두고 상태 파일에 적는다
  local LC_ALL=C old left stale=0 purge=0
  # 쓰는 길: 폴더를 본인만 쓰게 고친다. 다만 고치기 «전» 에 본인만 쓰는 폴더가 아니었다면 그 안에
  # 있던 것은 누가 넣었는지 알 수 없다 — 전부 지우고, 비었는지 확인한 뒤에만 0700 으로 만든다.
  # 순서가 중요하다: arm 폴더가 «정확히 0700» 이 되는 것은 비운 «뒤» 다. 그 전에는 읽는 길이 받지
  # 않는 권한(0710 · 못 비웠으면 0000)으로 둔다 — 지우기가 실패하든 도중에 끊기든, 다음 arm 은
  # 이 폴더를 다시 «본인만 쓰던 폴더가 아님» 으로 보고 지우기부터 하고, 그 사이 capture 는 거부한다.
  if [ -e "$HOME/.thiscode" ] || [ -L "$HOME/.thiscode" ]; then dir_is_private "$HOME/.thiscode" || stale=1; fi
  if [ -e "$ARM_DIR" ] || [ -L "$ARM_DIR" ]; then dir_is_private "$ARM_DIR" || stale=1; fi
  # 링크를 거쳐서는 지우지 않는다(~/.thiscode 나 arm 폴더가 링크면 아래 private_dir 이 거부한다)
  if [ "$stale" = 1 ] && [ ! -L "$HOME/.thiscode" ] && [ ! -L "$ARM_DIR" ] && [ -d "$ARM_DIR" ] && [ -O "$ARM_DIR" ]; then
    purge=1
    chmod 710 "$ARM_DIR" 2>/dev/null || return 1
  fi
  private_dir "$HOME/.thiscode" || return 1
  if [ "$purge" = 1 ]; then
    for old in "$ARM_DIR"/* "$ARM_DIR"/.[!.]* "$ARM_DIR"/..?*; do
      [ -e "$old" ] || [ -L "$old" ] || continue
      if [ -L "$old" ]; then
        rm -f -- "$old" 2>/dev/null    # 링크는 링크만 지운다(따라가지 않는다)
      else
        rm -rf -- "$old" 2>/dev/null   # 폴더째 지운다(rm 은 폴더 안의 링크를 따라가지 않는다)
      fi
    done
    # 지우기 명령의 결과가 아니라 «비었는가» 를 본다
    left="$(ls -A "$ARM_DIR" 2>/dev/null)" || left='?'
    if [ -n "$left" ]; then
      left=''
      chmod 000 "$ARM_DIR" 2>/dev/null
      ARM_WHY='blocked'
      return 1
    fi
  fi
  private_dir "$ARM_DIR" || return 1
  if [ -L "$ARM_FILE" ] || [ -e "$ARM_FILE" ]; then
    rm -f "$ARM_FILE" 2>/dev/null || return 1   # 링크면 링크만 지운다(따라가지 않는다)
  fi
  ARM_NONCE="$(od -An -N16 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')"
  [[ "$ARM_NONCE" =~ ^[0-9a-f]{32}$ ]] || return 1
  ( umask 077; set -o noclobber
    printf 'nonce=%s\nbot=%s\narmed_at=%s\n' "$ARM_NONCE" "$BOT" "$(date +%s)" > "$ARM_FILE" ) 2>/dev/null || return 1
  private_file "$ARM_FILE"
}

arm_read() {   # 믿을 수 있는 기록이면 ARM_NONCE 를 채운다. 아니면 not_armed 로 끝낸다
  local LC_ALL=C key value nonce='' bot='' at='' now age
  # 읽는 길: 기록을 읽기 «전» 에 그것이 놓인 폴더(~/.thiscode 와 그 안의 arm 폴더)와 파일을 «확인만» 한다.
  # 여기서는 권한을 고치지 않는다 — 고친 뒤 믿으면, 고치기 전에 남이 넣어 둔 기록을 받아들이게 된다.
  # 고치는 것은 arm(쓰는 길)뿐이다. 폴더 확인에서 거부할 때는 폴더 안의 것을 건드리지 않는다.
  # 폴더 확인을 지난 뒤 다른 봇의 기록 · 기한이 지난 기록 · 깨진 기록은 그 기록을 지운다.
  if [ ! -e "$HOME/.thiscode" ] && [ ! -L "$HOME/.thiscode" ]; then
    not_armed "이 봇으로 arm 한 기록이 없습니다"
  fi
  if [ ! -e "$ARM_DIR" ] && [ ! -L "$ARM_DIR" ]; then
    not_armed "이 봇으로 arm 한 기록이 없습니다"
  fi
  dir_is_private "$HOME/.thiscode" && dir_is_private "$ARM_DIR" \
    || not_armed "arm 기록 폴더가 본인만 쓰는 폴더가 아니라 그 안의 기록을 믿지 않습니다"
  if [ -L "$ARM_FILE" ] || [ ! -e "$ARM_FILE" ]; then
    not_armed "이 봇으로 arm 한 기록이 없습니다"
  fi
  file_is_private "$ARM_FILE" || not_armed "arm 기록을 믿을 수 없습니다"
  while IFS='=' read -r key value; do
    case "$key" in
      nonce) nonce="$value" ;;
      bot) bot="$value" ;;
      armed_at) at="$value" ;;
    esac
  done < "$ARM_FILE"
  if ! [[ "$nonce" =~ ^[0-9a-f]{32}$ ]] || ! [[ "$at" =~ ^[0-9]{1,12}$ ]]; then
    rm -f "$ARM_FILE" 2>/dev/null
    not_armed "arm 기록이 깨졌습니다"
  fi
  if [ "$bot" != "$BOT" ]; then
    rm -f "$ARM_FILE" 2>/dev/null
    not_armed "arm 기록이 다른 봇의 것입니다"
  fi
  now="$(date +%s)"
  age=$(( now - at ))
  if [ "$age" -lt 0 ] || [ "$age" -gt $(( ARM_TTL_MIN * 60 )) ]; then
    rm -f "$ARM_FILE" 2>/dev/null
    not_armed "arm 한 지 ${ARM_TTL_MIN}분이 지났습니다"
  fi
  ARM_NONCE="$nonce"
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
  if [ -z "$V" ]; then
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

unsafe() {   # $1 = 까닭 한 줄
  echo "❌ $1" >&2
  echo "사유 코드: check-failed" >&2
  return 3
}

# .env 는 본인만 읽는다. 다른 키는 그대로 두고 DISCORD_BOT_TOKEN 줄만 바꾼다.
save_value() {
  local tmp
  umask 077
  if [ -L "$BOT_DIR" ] || [ -L "$ENV_FILE" ]; then
    unsafe "봇 폴더나 .env 가 심볼릭 링크라 쓰지 않습니다 — $BOT_DIR"; return 3
  fi
  private_dir "$BOT_DIR" || { unsafe "봇 폴더를 본인만 쓰게 만들 수 없습니다(권한이나 ACL 을 못 고침) — $BOT_DIR"; return 3; }
  if [ -e "$ENV_FILE" ] && { [ ! -f "$ENV_FILE" ] || [ ! -O "$ENV_FILE" ]; }; then
    unsafe ".env 가 일반 파일이 아니거나 내 파일이 아니라 쓰지 않습니다 — $ENV_FILE"; return 3
  fi
  tmp="$(mktemp "$BOT_DIR/.env.XXXXXX")" || { unsafe "임시 파일을 못 만들었습니다 — $BOT_DIR"; return 3; }
  # 값을 쓰기 «전에» 임시 파일을 본인만 읽게 만든다(상속된 ACL 도 여기서 지운다)
  private_file "$tmp" || { rm -f "$tmp"; unsafe "임시 파일을 본인만 읽게 만들 수 없습니다 — 저장하지 않았습니다"; return 3; }
  if [ -f "$ENV_FILE" ]; then
    command grep -v '^DISCORD_BOT_TOKEN=' "$ENV_FILE" > "$tmp" 2>/dev/null || true
  fi
  printf 'DISCORD_BOT_TOKEN=%s\n' "$V" >> "$tmp" || { rm -f "$tmp"; unsafe "저장하지 못했습니다"; return 3; }
  mv -f "$tmp" "$ENV_FILE" || { rm -f "$tmp"; unsafe "저장하지 못했습니다"; return 3; }
  if ! private_file "$ENV_FILE"; then
    # 본인만 읽게 만들지 못한 파일에 토큰을 남기지 않는다
    rm -f "$ENV_FILE" 2>/dev/null
    unsafe ".env 를 본인만 읽게 만들 수 없어 지웠습니다(권한이나 ACL 을 못 고침) — $ENV_FILE"; return 3
  fi
  echo "✅ 토큰 저장 — 길이 ${#V}자 (값은 출력하지 않습니다) · $ENV_FILE"
  return 0
}

case "$MODE" in
  arm)
    bot_dir
    pick_clipboard
    if ! arm_write; then
      if [ "$ARM_WHY" = blocked ]; then
        # 안 지워진 것의 이름은 찍지 않는다(남이 넣은 이름을 화면에 옮기지 않는다)
        unsafe "arm 기록 폴더에 지울 수 없는 것이 있어 멈췄습니다(폴더는 못 쓰게 닫아 두었습니다) — 폴더를 옮긴 뒤 다시: mv ~/.thiscode/token-arm ~/.thiscode/token-arm.removed"
        exit 3
      fi
      rm -f "$ARM_FILE" 2>/dev/null
      unsafe "arm 기록을 본인만 읽게 남길 수 없습니다 — $ARM_DIR"
      exit 3
    fi
    if ! printf '%s:%s' "$MARKER" "$ARM_NONCE" | clip_write; then
      rm -f "$ARM_FILE" 2>/dev/null
      echo "❌ 클립보드에 쓰지 못했습니다" >&2; echo "사유 코드: tool-error" >&2; exit 4
    fi
    ARM_NONCE=''
    echo "🔒 준비됨($BOT) — 이제 포털의 «복사» 버튼을 누릅니다. ${ARM_TTL_MIN}분 안에 capture 를 부르세요(이 준비는 한 번만 쓰입니다)."
    ;;
  capture)
    bot_dir
    pick_clipboard
    arm_read   # 기록이 없거나 · 다른 봇 · 시간이 지났으면 여기서 끝난다(클립보드를 읽기 전)
    V="$(clip_read 2>/dev/null)" || { echo "❌ 클립보드를 읽지 못했습니다" >&2; echo "사유 코드: tool-error" >&2; exit 4; }
    V="${V%$'\r'}"
    if [ "$V" = "$MARKER:$ARM_NONCE" ]; then
      # 아직 아무것도 복사되지 않았다 — 기록은 남겨 둔다(시간 안에서 다시 capture 할 수 있다)
      V=''; ARM_NONCE=''
      echo "❌ 복사된 값이 없습니다 — 포털의 «복사» 버튼이 눌리지 않았습니다(저장하지 않았습니다)." >&2
      echo "사유 코드: clipboard-empty" >&2
      exit 1
    fi
    # 표식이 아닌 값을 읽었다 — 이 arm 은 여기서 쓰인 것이다(성공이든 아니든 다시 못 쓴다)
    ARM_NONCE=''
    rm -f "$ARM_FILE" 2>/dev/null
    if ! check_value; then
      # 토큰이 섞였을 수 있는 값을 클립보드에 남기지 않는다
      clip_clear >/dev/null 2>&1 || true
      V=''
      exit 1
    fi
    save_value; rc=$?
    V=''
    [ "$rc" -eq 0 ] || exit "$rc"
    if ! clip_clear >/dev/null 2>&1; then
      echo "⚠️ 토큰은 저장됐지만 클립보드를 비우지 못했습니다 — 지금 다른 글자를 한 번 복사해 덮어 주세요. 그 전까지는 끝난 것으로 보지 않습니다." >&2
      echo "사유 코드: tool-error" >&2
      exit 5
    fi
    ;;
  paste)
    bot_dir
    # 실수로 파이프로 부르는 것을 막는 검사다. 사람인지를 확인하는 것이 아니다(머리 주석 ②).
    if [ ! -t 0 ]; then
      echo "❌ 이 길은 사용자가 «자기 터미널» 에서 직접 실행합니다(여기는 터미널이 아닙니다)." >&2
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
