#!/usr/bin/env bash
# thiscode installer
# Environment: WSL Ubuntu / Linux native / macOS — auto-detected and branched
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<owner>/thiscode/main/install.sh | bash
#   or: git clone, then ./install.sh
#
# 10 steps (Zettelkasten WSL2-tmux guide + Codex + Obsidian CLI):
#   1.   Environment detection (OS / WSL / package manager)
#   2.   Base packages (tmux, git, curl, jq, build-essential)
#   3.   nvm + Node.js LTS
#   4.   Claude Code global install
#   4.5  Codex CLI global install (@openai/codex) — codex-layer dependency
#   5.   oh-my-tmux (gpakosz/.tmux) auto-install
#   6.   (optional) Apply thiscode tmux.conf.local
#   6.5  Obsidian CLI local setup — search execution belongs to /km:search
#   7.   thiscode plugin automatic install (user scope, manual fallback)
#   8.   First-bot wizard guidance (Claude Code, /thiscode:start)

set -euo pipefail

# ---------------------------------------------------------------- colors

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

log()  { printf "${BLUE}[thiscode]${NC} %s\n" "$*"; }
ok()   { printf "  ${GREEN}✓${NC} %s\n" "$*"; }
warn() { printf "  ${YELLOW}⚠${NC} %s\n" "$*"; }
err()  { printf "  ${RED}✗${NC} %s\n" "$*" >&2; }
step() { printf "\n${BOLD}${BLUE}━━━ Step %s/10 ━━━${NC} ${BOLD}%s${NC}\n" "$1" "$2"; }

# ---------------------------------------------------------------- globals

ENV_KIND=""    # wsl / linux / macos
PKG_MGR=""     # apt / dnf / yum / brew / pacman
REPO_DIR=""    # thiscode repo root (populated by git clone path if curl-piped)

# ---------------------------------------------------------------- Step 1

detect_env() {
  step 1 "Environment detection"

  local os
  os="$(uname -s)"
  case "$os" in
    Linux)
      if grep -qi microsoft /proc/version 2>/dev/null; then
        ENV_KIND="wsl"
        ok "WSL detected (Windows Subsystem for Linux)"
      else
        ENV_KIND="linux"
        ok "Linux native detected"
      fi
      ;;
    Darwin)
      ENV_KIND="macos"
      ok "macOS detected"
      ;;
    *)
      err "Unsupported OS: $os (only Linux / macOS / WSL supported)"
      exit 1
      ;;
  esac

  if   command -v apt-get >/dev/null 2>&1; then PKG_MGR="apt"
  elif command -v dnf     >/dev/null 2>&1; then PKG_MGR="dnf"
  elif command -v yum     >/dev/null 2>&1; then PKG_MGR="yum"
  elif command -v brew    >/dev/null 2>&1; then PKG_MGR="brew"
  elif command -v pacman  >/dev/null 2>&1; then PKG_MGR="pacman"
  else
    err "No supported package manager found (need one of: apt / dnf / yum / brew / pacman)"
    exit 1
  fi
  ok "Package manager: $PKG_MGR"
}

# ---------------------------------------------------------------- Step 2

install_base_packages() {
  step 2 "Base packages (tmux + git + curl + jq + build tools)"

  case "$PKG_MGR" in
    apt)
      sudo apt-get update -qq
      sudo apt-get install -y -qq tmux git curl jq build-essential
      ;;
    dnf)
      sudo dnf install -y -q tmux git curl jq gcc make
      ;;
    yum)
      sudo yum install -y -q tmux git curl jq gcc make
      ;;
    brew)
      brew list tmux >/dev/null 2>&1 || brew install tmux
      brew list git  >/dev/null 2>&1 || brew install git
      brew list curl >/dev/null 2>&1 || brew install curl
      brew list jq   >/dev/null 2>&1 || brew install jq
      ;;
    pacman)
      sudo pacman -S --noconfirm --needed tmux git curl jq base-devel
      ;;
  esac

  ok "tmux: $(tmux -V)"
  ok "git: $(git --version | head -1)"
}

# ---------------------------------------------------------------- Step 3

install_node() {
  step 3 "nvm + Node.js LTS"

  if command -v node >/dev/null 2>&1; then
    ok "Node.js already installed: $(node --version) → skip"
    return
  fi

  if [ ! -d "$HOME/.nvm" ]; then
    log "Installing nvm (v0.40.1)"
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  else
    ok "nvm already installed"
  fi

  # Activate nvm in current shell
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  # shellcheck disable=SC1091
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

  log "Installing Node.js LTS"
  nvm install --lts
  nvm use --lts

  ok "Node.js: $(node --version)"
  warn "Open a new terminal so nvm/node land permanently in PATH"
}

# ---------------------------------------------------------------- Step 4

install_claude_code() {
  step 4 "Claude Code (Anthropic official CLI)"

  if command -v claude >/dev/null 2>&1; then
    ok "Claude Code already installed: $(claude --version) → skip"
    return
  fi

  # Activate nvm (assumed same shell as Step 3)
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  # shellcheck disable=SC1091
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

  npm install -g @anthropic-ai/claude-code

  ok "Claude Code: $(claude --version)"
  warn "Before continuing, run 'claude auth login' in another terminal to complete browser auth"
}

# ---------------------------------------------------------------- Step 5

install_oh_my_tmux() {
  step 5 "oh-my-tmux (gpakosz/.tmux)"

  if [ -d "$HOME/.tmux" ] && [ -L "$HOME/.tmux.conf" ]; then
    ok "oh-my-tmux already installed (~/.tmux + ~/.tmux.conf symlink) → skip"
    return
  fi

  cd "$HOME"

  if [ ! -d "$HOME/.tmux" ]; then
    git clone --single-branch https://github.com/gpakosz/.tmux.git
  fi

  ln -s -f .tmux/.tmux.conf .tmux.conf

  if [ ! -f "$HOME/.tmux.conf.local" ]; then
    cp .tmux/.tmux.conf.local .
    ok "~/.tmux.conf.local created (user override file)"
  else
    ok "~/.tmux.conf.local preserved (existing file kept)"
  fi

  ok "oh-my-tmux installed"
  warn "tmux TERM env var should be xterm-256color (verify: echo \$TERM)"
}

# ---------------------------------------------------------------- Step 6

apply_our_tmux_conf() {
  step 6 "Apply thiscode tmux.conf.local (optional)"

  local src="$REPO_DIR/configs/tmux.conf.local"

  if [ -z "$REPO_DIR" ] || [ ! -f "$src" ]; then
    warn "thiscode repo not present locally → skipping this step (re-runnable after Step 7 git clone)"
    return
  fi

  if [ ! -t 0 ]; then
    # Non-interactive run (e.g. curl | bash) — no terminal to answer a prompt, so
    # don't block waiting on stdin. Keep the existing (safe) default of not
    # touching ~/.tmux.conf.local, but surface why this step was skipped.
    warn "Non-interactive run detected (no TTY on stdin) → skipping optional tmux.conf.local step, keeping any existing ~/.tmux.conf.local untouched. Re-run install.sh directly in a terminal to apply thiscode's tmux.conf.local."
    return
  fi

  if [ -f "$HOME/.tmux.conf.local" ]; then
    warn "You already have ~/.tmux.conf.local. Applying thiscode's version will back it up to ~/.tmux.conf.local.bak and then replace it."
    printf "\n  Back up and apply thiscode's tmux.conf.local? (Y/n) "
    read -r ans
    if [[ "$ans" =~ ^[Nn]$ ]]; then
      ok "Kept your existing ~/.tmux.conf.local — skipping this step"
      return
    fi
    cp "$HOME/.tmux.conf.local" "$HOME/.tmux.conf.local.bak"
    ok "Backed up existing file: ~/.tmux.conf.local.bak"
    cp "$src" "$HOME/.tmux.conf.local"
    ok "Applied thiscode's tmux.conf.local"
  else
    printf "\n  Use thiscode's tmux.conf.local? (y/N) "
    read -r ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
      cp "$src" "$HOME/.tmux.conf.local"
      ok "Applied thiscode's tmux.conf.local"
    else
      ok "Kept user override (~/.tmux.conf.local)"
    fi
  fi
}

# ---------------------------------------------------------------- Step 7

plugin_installed_scope() {
  local plugins_json

  plugins_json="$(claude plugin list --json 2>/dev/null)" || return 1
  printf '%s' "$plugins_json" | node -e '
    let input = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => { input += chunk; });
    process.stdin.on("end", () => {
      try {
        const plugins = JSON.parse(input);
        const found = Array.isArray(plugins) && plugins.find(
          (plugin) => plugin && plugin.id === "thiscode@thiscode-marketplace"
        );
        if (!found) process.exit(1);
        process.stdout.write(String(found.scope || "unknown"));
      } catch {
        process.exit(1);
      }
    });
  '
}

last_nonempty_line() {
  local text="$1"
  local candidate=""
  local last=""

  while IFS= read -r candidate; do
    [ -n "$candidate" ] && last="$candidate"
  done <<< "$text"
  printf '%s' "${last:-unknown error}"
}

print_plugin_manual_fallback() {
  local reason="$1"

  warn "Automatic thiscode plugin install could not finish: $reason"
  cat <<'EOF'

  Manual fallback — inside Claude Code, run:

      /plugin marketplace add treylom/ThisCode
      /plugin install thiscode@thiscode-marketplace

EOF
}

print_plugin_ready_guidance() {
  cat <<'EOF'

  Where to start (these are entry points, not the whole set):

      /thiscode:help           — LIST EVERY command and skill, with descriptions
      /thiscode:start          — main wizard (env + bot + first chat)
      /thiscode:install-hooks  — skill: SessionStart + UserPromptSubmit hook merge
      /thiscode:create-bot     — new-bot directory + .env + soul.md auto-setup
      /thiscode:open-meeting   — new meeting folder (multi-bot 4-file pattern)
      …

  Slash surfaces come from two places — commands/*.md AND skills/<name>/SKILL.md
  — so no fixed list here can stay accurate. Run /thiscode:help after install;
  it enumerates both directories at runtime.

  Prereq: jq (auto-installed in Step 2) — used by hook-merge slash commands
  for safe settings.json merging.

EOF
}

install_plugin() {
  step 7 "thiscode plugin automatic install"

  if ! command -v claude >/dev/null 2>&1; then
    print_plugin_manual_fallback "Claude Code executable was not found in PATH"
    return 0
  fi

  local installed_scope
  if installed_scope="$(plugin_installed_scope)"; then
    ok "thiscode plugin already installed (scope: $installed_scope) → skip"
    print_plugin_ready_guidance
    warn "On a vanilla Claude Code, run the /thiscode:install-hooks skill first (prevents orphan soul.md regression when SessionStart hook is absent)"
    return 0
  fi

  local output
  log "Adding the thiscode marketplace (user scope)"
  if ! output="$(claude plugin marketplace add treylom/ThisCode --scope user 2>&1)"; then
    print_plugin_manual_fallback "$(last_nonempty_line "$output")"
    return 0
  fi
  ok "thiscode marketplace ready"

  log "Installing thiscode@thiscode-marketplace (user scope)"
  if ! output="$(claude plugin install thiscode@thiscode-marketplace --scope user --yes 2>&1)"; then
    print_plugin_manual_fallback "$(last_nonempty_line "$output")"
    return 0
  fi

  if ! installed_scope="$(plugin_installed_scope)"; then
    print_plugin_manual_fallback "claude plugin list did not show thiscode@thiscode-marketplace after installation"
    return 0
  fi

  ok "thiscode plugin installed and verified (scope: $installed_scope)"
  print_plugin_ready_guidance
  warn "On a vanilla Claude Code, run the /thiscode:install-hooks skill first (prevents orphan soul.md regression when SessionStart hook is absent)"
}

# ---------------------------------------------------------------- Step 8

print_next_steps() {
  step 8 "First-bot wizard guidance"

  cat <<'EOF'

  ╔══════════════════════════════════════════════════════════════╗
  ║  Install complete — next steps                                 ║
  ╠══════════════════════════════════════════════════════════════╣
  ║                                                                ║
  ║  1. Start a new tmux session                                  ║
  ║       tmux new-session -s claude                              ║
  ║                                                                ║
  ║  2. Launch claude                                              ║
  ║       cd ~/<project> && claude                                ║
  ║                                                                ║
  ║  3. Start the wizard inside Claude Code                       ║
  ║       /thiscode:start                                         ║
  ║                                                                ║
  ║     The wizard walks you through:                              ║
  ║       - Discord bot creation (Developer Portal)               ║
  ║       - Bot token entry                                        ║
  ║       - First bot persona (soul.md template)                  ║
  ║       - Pairing + first-chat verification                     ║
  ║                                                                ║
  ║  4. If stuck, see the Troubleshooting section in README.md    ║
  ║                                                                ║
  ╚══════════════════════════════════════════════════════════════╝

EOF
}

# ---------------------------------------------------------------- main

main() {
  # Infer REPO_DIR from this script's location
  if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  fi

  log "thiscode install: starting"
  log "Detecting environment automatically"

  detect_env
  install_base_packages
  install_node
  install_claude_code
  install_codex_cli              # Step 4.5
  install_oh_my_tmux
  apply_our_tmux_conf
  install_obsidian_cli           # Step 6.5
  install_plugin
  print_next_steps

  log "thiscode install: finished"
}

# ---------------------------------------------------------------- Step 6.5

OBSIDIAN_VERSION_RESULT=""

obsidian_command_is_gui_app() {
  local command_path="$1"
  local resolved_path="$command_path"

  if command -v realpath >/dev/null 2>&1; then
    resolved_path="$(realpath "$command_path" 2>/dev/null || printf '%s' "$command_path")"
  elif [ -L "$command_path" ]; then
    resolved_path="$(readlink "$command_path" 2>/dev/null || printf '%s' "$command_path")"
  fi

  case "$command_path:$resolved_path" in
    *'/Obsidian.app/Contents/MacOS/'*|*'/Caskroom/obsidian/'*) return 0 ;;
    *) return 1 ;;
  esac
}

stop_process_group() {
  local parent_pid="$1"
  local process_group=""

  if command -v pkill >/dev/null 2>&1; then
    pkill -TERM -P "$parent_pid" 2>/dev/null || true
  fi
  process_group="$(ps -o pgid= -p "$parent_pid" 2>/dev/null | tr -d ' ')"
  if [ -n "$process_group" ] && [ "$process_group" = "$parent_pid" ]; then
    kill -TERM "-$process_group" 2>/dev/null || true
  else
    kill "$parent_pid" 2>/dev/null || true
  fi
}

obsidian_version_with_limit() {
  local command_path="$1"
  local output_file timeout_file child_pid guard_pid rc=0

  OBSIDIAN_VERSION_RESULT=""
  output_file="$(mktemp "${TMPDIR:-/tmp}/thiscode-obsidian-version.XXXXXX")" || return 1
  timeout_file="${output_file}.timeout"
  set -m
  "$command_path" --version >"$output_file" 2>&1 &
  child_pid=$!
  set +m
  (
    sleep 5
    if kill -0 "$child_pid" 2>/dev/null; then
      : >"$timeout_file"
      stop_process_group "$child_pid"
    fi
  ) >/dev/null 2>&1 &
  guard_pid=$!

  wait "$child_pid" || rc=$?
  stop_process_group "$guard_pid"
  wait "$guard_pid" 2>/dev/null || true
  if [ -f "$timeout_file" ]; then
    rm -f "$output_file" "$timeout_file"
    return 124
  fi
  OBSIDIAN_VERSION_RESULT="$(head -1 "$output_file")"
  rm -f "$output_file"
  [ "$rc" -eq 0 ] || return "$rc"
  [ -n "$OBSIDIAN_VERSION_RESULT" ] || OBSIDIAN_VERSION_RESULT='버전 출력 없음'
}

report_obsidian_command() {
  local command_path="$1"
  local label="$2"
  local version="" rc=0

  if obsidian_command_is_gui_app "$command_path"; then
    ok "Obsidian 앱 감지(버전 미확인)"
    return 0
  fi

  obsidian_version_with_limit "$command_path" || rc=$?
  version="$OBSIDIAN_VERSION_RESULT"
  if [ "$rc" -eq 0 ]; then
    ok "$label: $version"
  elif [ "$rc" -eq 124 ]; then
    warn "Obsidian 명령 감지(버전 확인 5초 초과)"
  else
    warn "Obsidian 명령 감지(버전 미확인, exit $rc)"
  fi
}

install_obsidian_cli() {
  local obsidian_command=""
  step "6.5" "Obsidian CLI (local tool setup; search via /km:search)"

  obsidian_command="$(command -v obsidian 2>/dev/null || true)"
  if [ -n "$obsidian_command" ]; then
    report_obsidian_command "$obsidian_command" "Obsidian CLI already installed"
    return
  fi

  case "$ENV_KIND" in
    macos)
      log "Installing Obsidian app (brew cask)"
      brew install --cask obsidian || warn "brew cask failed — install manually from https://obsidian.md/download"
      ;;
    wsl)
      warn "WSL environment — calling Windows-native Obsidian recommended:"
      cat <<'EOF'

  1. On Windows: download and run the Obsidian installer from https://obsidian.md/download
  2. Register a WSL alias:
       alias obsidian="'/mnt/c/Program Files/Obsidian/Obsidian.com'"
       # or add to ~/.bashrc
  3. WSL-side vault path:
       VAULT="/mnt/c/Users/<windows-user>/Documents/Obsidian/<vault-name>"

  See docs/04-obsidian-cli.md for details.

EOF
      ;;
    linux)
      log "Linux environment — 3 options:"
      cat <<'EOF'

  Option A — Snap (Ubuntu recommended):
       sudo snap install obsidian --classic

  Option B — Flatpak:
       flatpak install flathub md.obsidian.Obsidian

  Option C — AppImage / deb:
       Download manually from https://obsidian.md/download

EOF
      ;;
  esac

  # Verify
  obsidian_command="$(command -v obsidian 2>/dev/null || true)"
  if [ -n "$obsidian_command" ]; then
    report_obsidian_command "$obsidian_command" "Obsidian CLI"
  else
    warn "Obsidian CLI not installed — configure km separately and use /km:search for available search paths"
    warn "km order: GraphRAG → Obsidian CLI → Obsidian MCP → text search; this installer does not run that fallback"
    warn "If you don't use Obsidian, skipping this step is fine — most of thiscode still works"
  fi

  # Vault path env-var guidance
  log "Recommended vault path env var (add to ~/.bashrc or ~/.zshrc):"
  echo "  export OBSIDIAN_VAULT=\"\$HOME/Documents/<vault-name>\""
  echo "  # WSL: export OBSIDIAN_VAULT=\"/mnt/c/Users/<user>/Documents/Obsidian/<vault-name>\""
  echo ""
}

# ---------------------------------------------------------------- Step 4.5

install_codex_cli() {
  step "4.5" "Codex CLI (codex-layer dependency)"

  if command -v codex >/dev/null 2>&1; then
    ok "Codex CLI already installed: $(codex --version 2>&1 | head -1) → skip"
    return
  fi

  # Activate nvm (set up in Step 3)
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  # shellcheck disable=SC1091
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

  npm install -g @openai/codex

  ok "Codex CLI: $(codex --version 2>&1 | head -1)"
  warn "Before continuing, run 'codex login' in another terminal to complete OAuth auth"
  warn "After Claude Code install, run /thiscode:codex-check to verify"
}

if [ "${THISCODE_INSTALL_SH_SOURCE_ONLY:-0}" != "1" ]; then
  main "$@"
fi
