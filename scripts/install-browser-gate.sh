#!/usr/bin/env bash
# install-browser-gate.sh — Playwright 설치를 단계별로 실행하고 기계적으로 판정한다.
#
# Usage:
#   bash scripts/install-browser-gate.sh <0|1|2|3|4> [--check-only]
#   bash scripts/install-browser-gate.sh --self-test

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PROJECT_DIR="${THISCODE_BROWSER_PROJECT_DIR:-$PWD}"
CLAUDE_BIN="${THISCODE_BROWSER_CLAUDE:-claude}"
NPX_BIN="${THISCODE_BROWSER_NPX:-npx}"
MCP_NAME="${THISCODE_BROWSER_MCP_NAME:-playwright}"
TEST_URL="${THISCODE_BROWSER_TEST_URL:-https://example.com}"
INSTALL_GATE="$HERE/install-gate.sh"
CHECK_ONLY=0

pass() { printf '[PASS] %s\n' "$*"; }
note() { printf '[INFO] %s\n' "$*"; }
fail() {
  local step="$1" card="$2"; shift 2
  printf '[FAIL] %s단계 실패 → 수동 카드 %s\n' "$step" "$card" >&2
  printf '[CAUSE] %s\n' "$*" >&2
  return 1
}

command_exists() {
  if [[ "$1" == */* ]]; then [ -x "$1" ]; else command -v "$1" >/dev/null 2>&1; fi
}

os_kind() {
  local uname_s
  uname_s="${THISCODE_BROWSER_OS:-$(uname -s)}"
  case "$uname_s" in
    Darwin) printf 'macos' ;;
    Linux)
      if grep -qi microsoft /proc/version 2>/dev/null; then printf 'wsl'; else printf 'linux'; fi
      ;;
    MINGW*|MSYS*|CYGWIN*) printf 'windows' ;;
    *) printf 'unsupported:%s' "$uname_s" ;;
  esac
}

record_attempt() {
  local gate="$1" result="$2" reason="${3:-}"
  [ -x "$INSTALL_GATE" ] || return 0
  if [ "$result" = ok ]; then
    bash "$INSTALL_GATE" --attempted "$gate" ok >/dev/null 2>&1 || true
  else
    bash "$INSTALL_GATE" --attempted "$gate" fail "${reason:-unknown failure}" >/dev/null 2>&1 || true
  fi
}

step0_check() {
  local kind node_state=missing claude_state=missing
  kind="$(os_kind)"
  case "$kind" in unsupported:*) fail 0 A "지원하지 않는 운영체제(${kind#unsupported:})"; return 1;; esac
  command_exists node && node_state="$(node --version 2>/dev/null || printf present)"
  command_exists "$CLAUDE_BIN" && claude_state="$($CLAUDE_BIN --version 2>/dev/null | head -1 || printf present)"
  [ "$claude_state" != missing ] || { fail 0 A 'Claude Code 명령을 찾지 못했습니다'; return 1; }
  pass "0단계 환경 판정: os=$kind node=$node_state claude=$claude_state"
}

install_node_if_needed() {
  local kind
  command_exists node && command_exists npx && return 0
  [ "$CHECK_ONLY" -eq 0 ] || return 1
  kind="$(os_kind)"
  if [ "$kind" = windows ]; then
    if command_exists winget.exe; then
      winget.exe install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements || return 1
      export PATH="$PATH:/c/Program Files/nodejs"
    else
      return 1
    fi
  else
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    if [ ! -s "$NVM_DIR/nvm.sh" ]; then
      command_exists curl || return 1
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash || return 1
    fi
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh" || return 1
    nvm install --lts || return 1
    nvm use --lts || return 1
  fi
  command_exists node && command_exists npx
}

step1() {
  step0_check >/dev/null || return 1
  if install_node_if_needed; then
    pass "1단계 Node 준비: node=$(node --version) npx=$(npx --version)"
  else
    fail 1 B 'Node.js LTS와 npx를 자동 준비하지 못했습니다'
  fi
}

mcp_json_exact() {
  local config="$PROJECT_DIR/.mcp.json"
  [ -f "$config" ] || return 1
  node -e '
    const fs=require("fs");
    const p=process.argv[1], name=process.argv[2];
    try {
      const d=JSON.parse(fs.readFileSync(p,"utf8"));
      const m=d.mcpServers && d.mcpServers[name];
      process.exit(m && m.command==="npx" && Array.isArray(m.args) && m.args.length===1 && m.args[0]==="@playwright/mcp@latest" ? 0 : 1);
    } catch { process.exit(1); }
  ' "$config" "$MCP_NAME"
}

mcp_list_exact() {
  local cfg out rc
  cfg="${THISCODE_BROWSER_CLAUDE_CONFIG_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/thiscode-browser-claude.XXXXXX")}" || return 1
  out="$(cd "$PROJECT_DIR" && CLAUDE_CONFIG_DIR="$cfg" "$CLAUDE_BIN" mcp list 2>&1)"; rc=$?
  [ "$rc" -eq 0 ] || { printf '%s\n' "$out" >&2; return 1; }
  printf '%s\n' "$out" | awk -v prefix="${MCP_NAME}: npx @playwright/mcp@latest" '
    index($0, prefix) == 1 { found = 1 }
    END { exit found ? 0 : 1 }
  '
}

step2_check() {
  mcp_json_exact || { fail 2 C '프로젝트 설정의 Playwright 항목이 없거나 명령이 다릅니다'; return 1; }
  mcp_list_exact || { fail 2 C '`claude mcp list`의 프로젝트 Playwright 행을 확인하지 못했습니다'; return 1; }
  pass '2단계 프로젝트 MCP 등록 확인: scope=project command=npx @playwright/mcp@latest'
}

step2() {
  local cfg rc=0
  step1 >/dev/null || return 1
  if mcp_json_exact; then
    note '2단계 기존 프로젝트 등록을 그대로 사용합니다'
  else
    [ "$CHECK_ONLY" -eq 0 ] || { step2_check; return $?; }
    mkdir -p "$PROJECT_DIR"
    cfg="${THISCODE_BROWSER_CLAUDE_CONFIG_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/thiscode-browser-add.XXXXXX")}" || return 1
    if [ -x "$INSTALL_GATE" ]; then bash "$INSTALL_GATE" browser_mcp_registration >/dev/null 2>&1 || true; fi
    (cd "$PROJECT_DIR" && CLAUDE_CONFIG_DIR="$cfg" "$CLAUDE_BIN" mcp add -s project "$MCP_NAME" -- npx @playwright/mcp@latest) || rc=$?
    if [ "$rc" -ne 0 ]; then
      record_attempt browser_mcp_registration fail "claude mcp add exit $rc"
      fail 2 C "프로젝트 MCP 등록 명령이 exit $rc로 끝났습니다"
      return 1
    fi
    record_attempt browser_mcp_registration ok
  fi
  step2_check
}

browser_locations() {
  "$NPX_BIN" playwright install --dry-run chromium 2>&1 \
    | sed -n 's/^[[:space:]]*Install location:[[:space:]]*//p'
}

browser_locations_ready() {
  local locations loc count=0
  locations="$(browser_locations)" || return 1
  [ -n "$locations" ] || return 1
  while IFS= read -r loc; do
    [ -n "$loc" ] || continue
    count=$((count + 1))
    [ -d "$loc" ] || return 1
    if [ ! -f "$loc/INSTALLATION_COMPLETE" ] \
      && ! find "$loc" -type f -perm -111 -print -quit 2>/dev/null | grep -q .; then
      return 1
    fi
  done <<EOF
$locations
EOF
  [ "$count" -ge 2 ]
}

disk_preflight() {
  local avail floor=15728640
  [ "${THISCODE_BROWSER_SKIP_DISK_CHECK:-0}" = 1 ] && return 0
  avail="$(df -k "$PROJECT_DIR" | awk 'NR==2 {print $4}')"
  [ -n "$avail" ] && [ "$avail" -ge "$floor" ]
}

step3_check() {
  browser_locations_ready || { fail 3 D 'Chromium 설치 위치 또는 실행 파일을 확인하지 못했습니다'; return 1; }
  pass '3단계 브라우저 바이너리 확인: dry-run 위치 전건 실재'
}

step3() {
  local rc=0
  step2_check >/dev/null || return 1
  if browser_locations_ready; then
    note '3단계 기존 Chromium 바이너리를 그대로 사용합니다'
    step3_check
    return $?
  fi
  [ "$CHECK_ONLY" -eq 0 ] || { step3_check; return $?; }
  disk_preflight || { fail 3 D '여유 공간이 15 GiB 미만이라 안전상 다운로드를 시작하지 않았습니다'; return 1; }
  if [ -x "$INSTALL_GATE" ]; then bash "$INSTALL_GATE" browser_binary_install >/dev/null 2>&1 || true; fi
  "$NPX_BIN" playwright install chromium || rc=$?
  if [ "$rc" -ne 0 ]; then
    record_attempt browser_binary_install fail "playwright install exit $rc"
    fail 3 D "브라우저 설치 명령이 exit $rc로 끝났습니다"
    return 1
  fi
  record_attempt browser_binary_install ok
  step3_check
}

config_changes_keep_watched_keys() {
  local before_file="$1" after_file="$2"
  [ -f "$before_file" ] && [ -f "$after_file" ] || return 0
  node - "$before_file" "$after_file" <<'NODE'
const fs = require('fs');
const before = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const after = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const changed = [];

function kind(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  return typeof value;
}

function leaves(value, path) {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    const entries = Object.entries(value);
    if (entries.length === 0) changed.push(path);
    else for (const [key, child] of entries) leaves(child, [...path, key]);
  } else {
    changed.push(path);
  }
}

function walk(a, b, path = []) {
  if (kind(a) !== kind(b)) {
    changed.push(path);
    return;
  }
  if (a !== null && typeof a === 'object' && !Array.isArray(a)) {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const key of keys) {
      if (!Object.hasOwn(a, key)) leaves(b[key], [...path, key]);
      else if (!Object.hasOwn(b, key)) leaves(a[key], [...path, key]);
      else walk(a[key], b[key], [...path, key]);
    }
  } else if (Array.isArray(a)) {
    if (JSON.stringify(a) !== JSON.stringify(b)) changed.push(path);
  } else if (!Object.is(a, b)) {
    changed.push(path);
  }
}

walk(before, after);
const topLevelWatched = new Set([
  'mcpServers', 'hooks', 'permissions', 'allowedTools',
  'disabledTools', 'enabledTools', 'hasTrustDialogAccepted',
]);
const projectWatched = new Set([
  'mcpServers', 'mcpContextUris', 'enabledMcpjsonServers',
  'disabledMcpjsonServers', 'enabledMcpServers', 'disabledMcpServers',
  'allowedTools', 'disabledTools', 'enabledTools', 'hooks', 'permissions',
  'hasTrustDialogAccepted', 'hasClaudeMdExternalIncludesApproved',
  'hasClaudeMdExternalIncludesWarningShown', 'localSettingsSeenGitTracked',
]);
function watched(path) {
  if (path.length > 0 && topLevelWatched.has(path[0])) return true;
  return path.length >= 3 && path[0] === 'projects' && projectWatched.has(path[2]);
}

const unique = (paths) => [...new Map(paths.map((path) => [JSON.stringify(path), path])).values()]
  .sort((a, b) => a.join('.').localeCompare(b.join('.')));
const watchedChanges = unique(changed.filter(watched));
const otherChanges = unique(changed.filter((path) => !watched(path)));
for (const path of otherChanges) console.log('[WARN] 비감시 설정 변화: ' + path.join('.'));
if (watchedChanges.length > 0) {
  for (const path of watchedChanges) console.error('감시 설정 변화: ' + path.join('.'));
  process.exit(1);
}
NODE
}

step4_log_has_execution() {
  local log_file="$1"
  node - "$log_file" <<'NODE'
const fs = require('fs');
const path = process.argv[2];
const events = [];
for (const line of fs.readFileSync(path, 'utf8').split(/\r?\n/)) {
  if (!line.trim()) continue;
  try { events.push(JSON.parse(line)); } catch {}
}

const navigate = 'mcp__playwright__browser_navigate';
const snapshot = 'mcp__playwright__browser_snapshot';
const snapshotIds = new Set();
let navigateUses = 0;
let snapshotUses = 0;

function walk(value, visit) {
  if (Array.isArray(value)) {
    for (const item of value) walk(item, visit);
  } else if (value && typeof value === 'object') {
    visit(value);
    for (const item of Object.values(value)) walk(item, visit);
  }
}

for (const event of events) {
  walk(event, (value) => {
    if (value.type !== 'tool_use' || typeof value.id !== 'string') return;
    if (value.name === navigate) navigateUses += 1;
    if (value.name === snapshot) {
      snapshotUses += 1;
      snapshotIds.add(value.id);
    }
  });
}

function containsExampleDomain(value) {
  if (typeof value === 'string') return value.includes('Example Domain');
  if (Array.isArray(value)) return value.some(containsExampleDomain);
  if (value && typeof value === 'object') return Object.values(value).some(containsExampleDomain);
  return false;
}

let snapshotResultHasTitle = false;
for (const event of events) {
  walk(event, (value) => {
    if (value.type === 'tool_result'
        && snapshotIds.has(value.tool_use_id)
        && containsExampleDomain(value.content)) {
      snapshotResultHasTitle = true;
    }
  });
}

if (navigateUses < 1 || snapshotUses < 1 || !snapshotResultHasTitle) process.exit(1);
NODE
}

step4() {
  local cfg="" log rc=0 before_copy before_hash after_hash
  step3_check >/dev/null || return 1
  [ "$CHECK_ONLY" -eq 0 ] || { fail 4 E '실행 확인은 check-only로 대신할 수 없습니다'; return 1; }
  log="${THISCODE_BROWSER_LOG:-$(mktemp "${TMPDIR:-/tmp}/thiscode-browser-check.XXXXXX")}" || return 1
  before_copy="$(mktemp "${TMPDIR:-/tmp}/thiscode-browser-config-before.XXXXXX")" || return 1
  if [ -f "$HOME/.claude.json" ]; then cp "$HOME/.claude.json" "$before_copy"; fi
  before_hash="$(shasum -a 256 "$HOME/.claude.json" 2>/dev/null | awk '{print $1}')"
  if [ -n "${THISCODE_BROWSER_CLAUDE_CONFIG_DIR:-}" ]; then
    cfg="$THISCODE_BROWSER_CLAUDE_CONFIG_DIR"
    if [ -f "$HOME/.claude.json" ] && [ ! -f "$cfg/.claude.json" ]; then cp "$HOME/.claude.json" "$cfg/.claude.json"; fi
    (cd "$PROJECT_DIR" && CLAUDE_CONFIG_DIR="$cfg" "$CLAUDE_BIN" -p \
      --model sonnet --effort medium --output-format stream-json --verbose \
      --no-session-persistence --mcp-config "$PROJECT_DIR/.mcp.json" --strict-mcp-config \
      --permission-mode dontAsk \
      --allowedTools='mcp__playwright__browser_navigate,mcp__playwright__browser_snapshot' \
      "Playwright 도구만 사용합니다. ${TEST_URL}을 열고 페이지 스냅샷을 확인한 뒤 마지막 줄을 정확히 TITLE=Example Domain으로 출력합니다.") \
      >"$log" 2>&1 || rc=$?
  else
    (cd "$PROJECT_DIR" && "$CLAUDE_BIN" -p \
      --model sonnet --effort medium --output-format stream-json --verbose \
      --no-session-persistence --mcp-config "$PROJECT_DIR/.mcp.json" --strict-mcp-config \
      --permission-mode dontAsk \
      --allowedTools='mcp__playwright__browser_navigate,mcp__playwright__browser_snapshot' \
      "Playwright 도구만 사용합니다. ${TEST_URL}을 열고 페이지 스냅샷을 확인한 뒤 마지막 줄을 정확히 TITLE=Example Domain으로 출력합니다.") \
      >"$log" 2>&1 || rc=$?
  fi
  after_hash="$(shasum -a 256 "$HOME/.claude.json" 2>/dev/null | awk '{print $1}')"
  config_changes_keep_watched_keys "$before_copy" "$HOME/.claude.json" \
    || { fail 4 E '실행 중 MCP·권한·훅·신뢰 감시 설정이 변경되었습니다'; return 1; }
  if [ "$before_hash" != "$after_hash" ]; then
    note '감시 설정 변화는 0건입니다. 비감시 변경은 위 WARN 목록으로 남겼습니다'
  fi
  [ "$rc" -eq 0 ] || { fail 4 E "새 세션 실행이 exit ${rc}로 끝났습니다(로그: $log)"; return 1; }
  step4_log_has_execution "$log" \
    || { fail 4 E "도구 실행 이벤트와 스냅샷 제목 결과를 확인하지 못했습니다(로그: $log)"; return 1; }
  pass "4단계 새 세션 실행 확인: navigate+snapshot+TITLE, log=$log"
}

self_test() {
  local tmp fake project decoy cfg_before cfg_after cfg_out old_path passes=0 total=0 rc
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/thiscode-browser-selftest.XXXXXX")" || return 1
  fake="$tmp/bin"; project="$tmp/project"; mkdir -p "$fake" "$project"
  cat >"$fake/claude" <<'FAKE_CLAUDE'
#!/usr/bin/env bash
if [ "${1:-}" = --version ]; then echo '2.test'; exit 0; fi
if [ "${1:-}" = mcp ] && [ "${2:-}" = add ]; then
  cat >.mcp.json <<'JSON'
{"mcpServers":{"playwright":{"type":"stdio","command":"npx","args":["@playwright/mcp@latest"],"env":{}}}}
JSON
  exit 0
fi
if [ "${1:-}" = mcp ] && [ "${2:-}" = list ]; then
  case "${FAKE_MCP_LIST_VARIANT:-connected}" in
    connected) echo 'playwright: npx @playwright/mcp@latest - ✔ Connected' ;;
    localized) echo 'playwright: npx @playwright/mcp@latest - 연결됨' ;;
    no_status) echo 'playwright: npx @playwright/mcp@latest' ;;
    wrong_command) echo 'playwright: node @playwright/mcp@latest - ✔ Connected' ;;
    wrong_name) echo 'other: npx @playwright/mcp@latest - ✔ Connected' ;;
  esac
  exit 0
fi
printf '%s\n' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"nav-1","name":"mcp__playwright__browser_navigate"}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"nav-1","content":"Page URL: https://example.com"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"snap-1","name":"mcp__playwright__browser_snapshot"}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"snap-1","content":[{"type":"text","text":"Page Title: Example Domain"}]}]}}' \
  '{"type":"result","result":"TITLE=Example Domain"}'
FAKE_CLAUDE
  cat >"$fake/npx" <<FAKE_NPX
#!/usr/bin/env bash
if [ "\${1:-}" = playwright ] && [ "\${2:-}" = install ] && [ "\${3:-}" = --dry-run ]; then
  echo '  Install location:    $tmp/browsers/chromium'
  echo '  Install location:    $tmp/browsers/ffmpeg'
  echo '  Install location:    $tmp/browsers/headless'
  exit 0
fi
if [ "\${1:-}" = playwright ] && [ "\${2:-}" = install ]; then
  mkdir -p '$tmp/browsers/chromium' '$tmp/browsers/ffmpeg' '$tmp/browsers/headless'
  touch '$tmp/browsers/chromium/INSTALLATION_COMPLETE' '$tmp/browsers/ffmpeg/INSTALLATION_COMPLETE' '$tmp/browsers/headless/INSTALLATION_COMPLETE'
  exit 0
fi
exit 2
FAKE_NPX
  chmod +x "$fake/claude" "$fake/npx"
  old_path="$PATH"; export PATH="$fake:$PATH"
  export THISCODE_BROWSER_PROJECT_DIR="$project" THISCODE_BROWSER_CLAUDE="$fake/claude" THISCODE_BROWSER_NPX="$fake/npx"
  export THISCODE_BROWSER_SKIP_DISK_CHECK=1 THISCODE_INSTALL_STATE="$tmp/install-state.yaml" THISCODE_INSTALL_LOG="$tmp/install-log.jsonl"
  printf 'install:\n  mode: auto\n' >"$THISCODE_INSTALL_STATE"
  for s in 0 1 2 3 4; do
    total=$((total + 1)); if "$0" "$s" >/dev/null; then passes=$((passes + 1)); else echo "[SELFTEST FAIL] step $s" >&2; fi
  done
  node -e 'const fs=require("fs");const p=process.argv[1],d=JSON.parse(fs.readFileSync(p));d.mcpServers.playwright.args=["DOES-NOT-EXIST"];fs.writeFileSync(p,JSON.stringify(d));' "$project/.mcp.json"
  total=$((total + 1)); rc=0; "$0" 2 --check-only >/dev/null 2>&1 || rc=$?; [ "$rc" -ne 0 ] && passes=$((passes + 1))
  node -e 'const fs=require("fs");const p=process.argv[1],d=JSON.parse(fs.readFileSync(p));d.mcpServers.playwright.args=["@playwright/mcp@latest"];fs.writeFileSync(p,JSON.stringify(d));' "$project/.mcp.json"
  for variant in connected localized no_status; do
    total=$((total + 1)); FAKE_MCP_LIST_VARIANT="$variant"; export FAKE_MCP_LIST_VARIANT
    if mcp_list_exact; then passes=$((passes + 1)); else echo "[SELFTEST FAIL] mcp list $variant" >&2; fi
  done
  for variant in wrong_command wrong_name; do
    total=$((total + 1)); FAKE_MCP_LIST_VARIANT="$variant"; export FAKE_MCP_LIST_VARIANT
    rc=0; mcp_list_exact || rc=$?; [ "$rc" -ne 0 ] && passes=$((passes + 1))
  done
  unset FAKE_MCP_LIST_VARIANT
  decoy="$tmp/init-only.ndjson"
  printf '%s\n' \
    '{"type":"system","subtype":"init","tools":["mcp__playwright__browser_navigate","mcp__playwright__browser_snapshot"]}' \
    '{"type":"result","result":"TITLE=Example Domain"}' >"$decoy"
  total=$((total + 1)); rc=0; step4_log_has_execution "$decoy" || rc=$?; [ "$rc" -ne 0 ] && passes=$((passes + 1))
  cfg_before="$tmp/config-before.json"; cfg_after="$tmp/config-after.json"; cfg_out="$tmp/config-check.out"
  printf '%s\n' '{"mcpServers":{},"projects":{"/tmp/course":{"mcpServers":{},"enabledMcpjsonServers":[],"disabledMcpjsonServers":[]}}}' >"$cfg_before"

  printf '%s\n' '{"mcpServers":{"rogue":{"command":"false"}},"projects":{"/tmp/course":{"mcpServers":{},"enabledMcpjsonServers":[],"disabledMcpjsonServers":[]}}}' >"$cfg_after"
  total=$((total + 1)); rc=0; config_changes_keep_watched_keys "$cfg_before" "$cfg_after" >"$cfg_out" 2>&1 || rc=$?; [ "$rc" -ne 0 ] && grep -q '감시 설정 변화: mcpServers.rogue.command' "$cfg_out" && passes=$((passes + 1))

  printf '%s\n' '{"mcpServers":{},"projects":{"/tmp/course":{"mcpServers":{"rogue":{"command":"false"}},"enabledMcpjsonServers":[],"disabledMcpjsonServers":[]}}}' >"$cfg_after"
  total=$((total + 1)); rc=0; config_changes_keep_watched_keys "$cfg_before" "$cfg_after" >"$cfg_out" 2>&1 || rc=$?; [ "$rc" -ne 0 ] && grep -q '감시 설정 변화: projects./tmp/course.mcpServers.rogue.command' "$cfg_out" && passes=$((passes + 1))

  printf '%s\n' '{"mcpServers":{},"promptQueueUseCount":1,"skillUsage":{"thiscode:install-browser":{"lastUsedAt":1,"usageCount":1}},"projects":{"/tmp/course":{"mcpServers":{},"enabledMcpjsonServers":[],"disabledMcpjsonServers":[]}}}' >"$cfg_after"
  total=$((total + 1)); rc=0; config_changes_keep_watched_keys "$cfg_before" "$cfg_after" >"$cfg_out" 2>&1 || rc=$?; [ "$rc" -eq 0 ] && grep -q '\[WARN\] 비감시 설정 변화: promptQueueUseCount' "$cfg_out" && grep -q '\[WARN\] 비감시 설정 변화: skillUsage.thiscode:install-browser.usageCount' "$cfg_out" && passes=$((passes + 1))

  printf '%s\n' '{"mcpServers":{},"clientDataCacheSlots":{"slot":{"at":1}},"additionalModelOptionsCache":{},"migrationVersion":1,"additionalModelOptionsAnsweredAt":1,"projects":{"/tmp/course":{"mcpServers":{},"enabledMcpjsonServers":[],"disabledMcpjsonServers":[]}}}' >"$cfg_after"
  total=$((total + 1)); rc=0; config_changes_keep_watched_keys "$cfg_before" "$cfg_after" >"$cfg_out" 2>&1 || rc=$?; [ "$rc" -eq 0 ] && grep -q '\[WARN\] 비감시 설정 변화: migrationVersion' "$cfg_out" && grep -q '\[WARN\] 비감시 설정 변화: clientDataCacheSlots.slot.at' "$cfg_out" && passes=$((passes + 1))
  export PATH="$old_path"
  printf '[SELFTEST] %s/%s passed\n' "$passes" "$total"
  [ "$passes" -eq "$total" ]
}

if [ "${1:-}" = --self-test ]; then self_test; exit $?; fi
STEP="${1:-}"
[ "${2:-}" = --check-only ] && CHECK_ONLY=1
case "$STEP" in
  0) step0_check ;;
  1) step1 ;;
  2) step2 ;;
  3) step3 ;;
  4) step4 ;;
  *) echo 'usage: install-browser-gate.sh <0|1|2|3|4> [--check-only] | --self-test' >&2; exit 2 ;;
esac
