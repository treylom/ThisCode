import { progressEnv } from './progress.mjs';
import { join } from 'node:path';

function shQuote(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`;
}

export function setupFlowAliases({ product, repoRoot, botWd, stateDir, session, progressReportCadence }) {
  const prefix = product || 'thiscode';
  const sess = session || prefix;
  const yoloFile = `${stateDir}/.${prefix}-yolo`;
  const envPrefix = prefix.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
  const env = progressEnv({ cadence: progressReportCadence, prefix: envPrefix });
  const progressVars = `${envPrefix}_PROGRESS_CADENCE=${shQuote(env[`${envPrefix}_PROGRESS_CADENCE`])} ${envPrefix}_HEARTBEAT_SEC=${shQuote(env[`${envPrefix}_HEARTBEAT_SEC`])}`;
  const launcher = shQuote(join(botWd, '.thiscode-bot-launcher.sh'));
  return [
    '# Source this block from your shell, or paste it into your own rc file if you want it permanent.',
    '# First create this bot launcher with scripts/install-bot-launcher.mjs using the same confirmed bot paths.',
    `alias ${prefix}-start="cd ${shQuote(repoRoot)} && BOT_WD=${shQuote(botWd)} SESSION=${shQuote(sess)} ${progressVars} ${launcher} start"`,
    `alias ${prefix}-attach="tmux attach -t ${sess}"`,
    `alias ${prefix}-discord="cd ${shQuote(repoRoot)} && BOT_WD=${shQuote(botWd)} DISCORD_STATE_DIR=${shQuote(stateDir)} SESSION=${shQuote(sess)} ${progressVars} ${launcher} start"`,
    `alias ${prefix}-yolo-on="mkdir -p ${shQuote(stateDir)} && touch ${shQuote(yoloFile)}"`,
    `alias ${prefix}-yolo-off="rm -f ${shQuote(yoloFile)}"`,
  ].join('\n') + '\n';
}

export function setupFlowGuide(product = 'thiscode') {
  return [
    `${product} setup uses a tmux-only Discord bot flow.`,
    '1. Confirm repo root, BOT_WD, and Discord state dir, then create the bot launcher with scripts/install-bot-launcher.mjs before writing aliases.',
    '2. Start with safe mode. Use YOLO/danger-full-access only after explicit opt-in.',
    '3. Choose progress_report_cadence: per_task means meaningful subtask/milestone completion; 1m/3m/5m configure heartbeat; off disables heartbeat.',
    '4. Source the generated alias script/block yourself; add it to a shell rc file only if you want it permanent.',
    '5. Run the doctor command before reporting the bot ready.',
  ].join('\n');
}
