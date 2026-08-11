import {
  chmodSync,
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { dirname, isAbsolute, join } from 'node:path';

const CHANNELS = new Set(['discord', 'slack']);
const SAFE_NAME = /^[\p{L}\p{N}_][\p{L}\p{N}_-]{0,63}$/u;
const LAUNCHER_MARKER = '# thiscode-bot-launcher v1';

function shQuote(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`;
}

function regexEscape(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function requireText(value, name) {
  if (typeof value !== 'string' || !value || value.includes('\0') || /[\r\n]/.test(value)) {
    throw new Error(`${name} must be one non-empty line`);
  }
  return value;
}

function normalizeConfig(input, { requireExisting = false } = {}) {
  const channel = requireText(input.channel, 'channel');
  if (!CHANNELS.has(channel)) throw new Error('channel must be discord or slack');
  const aliasName = requireText(input.aliasName, 'aliasName');
  const sessionName = requireText(input.sessionName, 'sessionName');
  if (!SAFE_NAME.test(aliasName)) throw new Error('aliasName may contain letters, numbers, _ and - only');
  if (!SAFE_NAME.test(sessionName)) throw new Error('sessionName may contain letters, numbers, _ and - only');
  const botWd = requireText(input.botWd, 'botWd');
  const stateDir = requireText(input.stateDir, 'stateDir');
  const rcPath = input.rcPath ? requireText(input.rcPath, 'rcPath') : '';
  const wikiPath = input.wikiPath ? requireText(input.wikiPath, 'wikiPath') : '';
  for (const [key, value] of Object.entries({ botWd, stateDir, ...(rcPath ? { rcPath } : {}), ...(wikiPath ? { wikiPath } : {}) })) {
    if (!isAbsolute(value)) throw new Error(`${key} must be an absolute confirmed path`);
  }
  if (requireExisting) {
    for (const [key, value] of Object.entries({ botWd, stateDir })) {
      if (!existsSync(value) || !statSync(value).isDirectory()) throw new Error(`${key} is not an existing directory: ${value}`);
    }
  }
  return { channel, aliasName, sessionName, botWd, stateDir, rcPath, wikiPath };
}

export function launcherScript(input) {
  const cfg = normalizeConfig(input);
  const wikiExport = cfg.wikiPath
    ? `export THISCODE_WIKI_PATH=${shQuote(cfg.wikiPath)}`
    : ':';
  return `#!/usr/bin/env bash
${LAUNCHER_MARKER}
# Generated only from paths confirmed during /thiscode bot creation.
set -euo pipefail

CHANNEL=${shQuote(cfg.channel)}
SESSION_NAME=${shQuote(cfg.sessionName)}
BOT_WD=${shQuote(cfg.botWd)}
STATE_DIR=${shQuote(cfg.stateDir)}
ACTION="\${1:-start}"
SELF="\${BASH_SOURCE[0]}"
case "$SELF" in /*) ;; *) SELF="$PWD/$SELF" ;; esac

case "$ACTION" in start|safe|stop) ;; *)
  echo "usage: $SELF <start|safe|stop>" >&2
  exit 2
esac

stop_session() {
  if ! command -v tmux >/dev/null 2>&1; then
    echo "[thiscode] tmux 없음 — foreground 봇은 실행한 터미널에서 Ctrl-C로 끕니다."
    return 0
  fi
  if tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "=$SESSION_NAME"
    echo "[thiscode] '$SESSION_NAME' 세션을 종료했습니다."
  else
    echo "[thiscode] '$SESSION_NAME' 세션이 없습니다."
  fi
}

run_agent() {
  cd "$BOT_WD"
  if [ "$CHANNEL" = discord ]; then
    export DISCORD_STATE_DIR="$STATE_DIR"
    ${wikiExport}
    exec claude --channels plugin:discord@claude-plugins-official
  fi
  export CLAUDE_CHANNEL_SLACK_DIR="$STATE_DIR"
  if [ "$ACTION" = safe ]; then
    exec claude --dangerously-load-development-channels server:slack-channel
  fi
  exec claude --dangerously-skip-permissions --dangerously-load-development-channels server:slack-channel
}

if [ "$ACTION" = stop ]; then
  stop_session
  exit 0
fi

if [ "\${THISCODE_LAUNCH_INSIDE:-0}" = 1 ]; then
  run_agent
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "[thiscode] tmux 없음 — 확인된 WD에서 foreground로 시작합니다."
  run_agent
fi

if tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
  echo "[thiscode] '$SESSION_NAME' 이전 세션 정리 중..."
  tmux kill-session -t "=$SESSION_NAME"
  sleep 0.2
fi

printf -v INNER_CMD 'exec env THISCODE_LAUNCH_INSIDE=1 %q %q' "$SELF" "$ACTION"
tmux new-session -d -s "$SESSION_NAME" -n bot -c "$BOT_WD" "$INNER_CMD"

if [ "\${THISCODE_LAUNCH_DETACH:-0}" = 1 ] || [ ! -t 0 ] || [ ! -t 1 ]; then
  echo "[thiscode] '$SESSION_NAME' 시작됨 — attach: tmux attach -t '=$SESSION_NAME'"
  exit 0
fi
if [ -n "\${TMUX:-}" ]; then
  exec tmux switch-client -t "=$SESSION_NAME"
fi
exec tmux attach-session -t "=$SESSION_NAME"
`;
}

export function managedRcBlock(input, launcherPath) {
  const cfg = normalizeConfig(input);
  const start = `${shQuote(launcherPath)} start`;
  const stop = `${shQuote(launcherPath)} stop`;
  const lines = [
    `# >>> thiscode bot launcher:${cfg.aliasName} >>>`,
    '# Generated from confirmed paths. Re-run the installer to update this managed block.',
    `alias ${cfg.aliasName}=${shQuote(start)}`,
    `alias ${cfg.aliasName}-stop=${shQuote(stop)}`,
  ];
  if (cfg.channel === 'slack') {
    lines.push(`alias ${cfg.aliasName}-safe=${shQuote(`${shQuote(launcherPath)} safe`)}`);
  }
  lines.push(`# <<< thiscode bot launcher:${cfg.aliasName} <<<`);
  return lines.join('\n') + '\n';
}

function updateRc(existing, cfg, block) {
  const start = `# >>> thiscode bot launcher:${cfg.aliasName} >>>`;
  const end = `# <<< thiscode bot launcher:${cfg.aliasName} <<<`;
  const pattern = new RegExp(`${regexEscape(start)}[\\s\\S]*?${regexEscape(end)}\\n?`, 'g');
  const hadStart = existing.includes(start);
  const hadEnd = existing.includes(end);
  if (hadStart !== hadEnd) throw new Error(`incomplete managed rc block for ${cfg.aliasName}`);
  const outside = existing.replace(pattern, '');
  for (const name of [cfg.aliasName, `${cfg.aliasName}-stop`, `${cfg.aliasName}-safe`]) {
    const collision = new RegExp(`(^|\\n)\\s*alias\\s+${regexEscape(name)}=`);
    if (collision.test(outside)) throw new Error(`rc already defines alias outside the managed block: ${name}`);
  }
  if (hadStart) return existing.replace(pattern, block);
  const prefix = existing && !existing.endsWith('\n') ? `${existing}\n` : existing;
  return `${prefix}${prefix ? '\n' : ''}${block}`;
}

function backupPath(path) {
  const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14);
  let candidate = `${path}.thiscode-backup-${stamp}`;
  let n = 1;
  while (existsSync(candidate)) candidate = `${path}.thiscode-backup-${stamp}-${n++}`;
  return candidate;
}

function atomicWrite(path, text, mode) {
  const temp = `${path}.thiscode-tmp-${process.pid}`;
  writeFileSync(temp, text, { mode });
  chmodSync(temp, mode);
  renameSync(temp, path);
}

export function installBotLauncher(input) {
  const cfg = normalizeConfig(input, { requireExisting: Boolean(input.apply) });
  const launcherPath = join(cfg.botWd, '.thiscode-bot-launcher.sh');
  const script = launcherScript(cfg);
  const block = managedRcBlock(cfg, launcherPath);
  if (!input.apply) return { launcherPath, script, rcBlock: block, applied: false };
  if (!cfg.rcPath) throw new Error('rcPath is required with apply=true');
  if (existsSync(launcherPath) && !readFileSync(launcherPath, 'utf8').includes(LAUNCHER_MARKER)) {
    throw new Error(`refusing to overwrite an unmanaged launcher: ${launcherPath}`);
  }
  mkdirSync(dirname(cfg.rcPath), { recursive: true });
  const rcExists = existsSync(cfg.rcPath);
  const currentRc = rcExists ? readFileSync(cfg.rcPath, 'utf8') : '';
  const nextRc = updateRc(currentRc, cfg, block);
  let backup = '';
  if (rcExists) {
    backup = backupPath(cfg.rcPath);
    writeFileSync(backup, currentRc, { mode: statSync(cfg.rcPath).mode & 0o777 });
  }
  atomicWrite(launcherPath, script, 0o755);
  atomicWrite(cfg.rcPath, nextRc, rcExists ? statSync(cfg.rcPath).mode & 0o777 : 0o600);
  return { launcherPath, rcPath: cfg.rcPath, backupPath: backup, rcBlock: block, applied: true };
}
