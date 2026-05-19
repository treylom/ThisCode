function shQuote(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`;
}

export function setupFlowAliases({ product, repoRoot, botWd, stateDir, session }) {
  const prefix = product || 'thiscode';
  const sess = session || prefix;
  const yoloFile = `${stateDir}/.${prefix}-yolo`;
  return [
    `alias ${prefix}-start="cd ${shQuote(repoRoot)} && BOT_WD=${shQuote(botWd)} SESSION=${shQuote(sess)} ./scripts/launch.sh"`,
    `alias ${prefix}-attach="tmux attach -t ${sess}"`,
    `alias ${prefix}-discord="cd ${shQuote(repoRoot)} && BOT_WD=${shQuote(botWd)} DISCORD_STATE_DIR=${shQuote(stateDir)} SESSION=${shQuote(sess)} ./scripts/launch.sh"`,
    `alias ${prefix}-yolo-on="mkdir -p ${shQuote(stateDir)} && touch ${shQuote(yoloFile)}"`,
    `alias ${prefix}-yolo-off="rm -f ${shQuote(yoloFile)}"`,
  ].join('\n') + '\n';
}

export function setupFlowGuide(product = 'thiscode') {
  return [
    `${product} setup uses a tmux-only Discord bot flow.`,
    '1. Confirm repo root, BOT_WD, and Discord state dir before writing aliases.',
    '2. Start with safe mode. Use YOLO/danger-full-access only after explicit opt-in.',
    '3. Choose progress_report_cadence: per_task, 1m, 3m, 5m, off, or custom.',
    '4. Run the doctor command before reporting the bot ready.',
  ].join('\n');
}
