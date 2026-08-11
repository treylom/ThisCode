#!/usr/bin/env node
import { homedir } from 'node:os';
import { join } from 'node:path';
import { installBotLauncher } from './lib/bot-launcher.mjs';

const args = process.argv.slice(2);
const has = flag => args.includes(flag);
const arg = name => {
  const inline = args.find(value => value.startsWith(`${name}=`));
  if (inline) return inline.slice(name.length + 1);
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] && !args[index + 1].startsWith('--') ? args[index + 1] : '';
};

if (has('--help')) {
  console.log('Usage: node scripts/install-bot-launcher.mjs --channel discord|slack --alias <word> --session <name> --bot-wd <absolute> --state-dir <absolute> [--wiki-path <absolute>] [--rc <absolute>] [--yes]');
  process.exit(0);
}

const shell = process.env.SHELL || '';
const defaultRc = join(homedir(), shell.endsWith('/zsh') ? '.zshrc' : '.bashrc');

try {
  const result = installBotLauncher({
    channel: arg('--channel'),
    aliasName: arg('--alias'),
    sessionName: arg('--session'),
    botWd: arg('--bot-wd'),
    stateDir: arg('--state-dir'),
    wikiPath: arg('--wiki-path'),
    rcPath: arg('--rc') || defaultRc,
    apply: has('--yes'),
  });
  if (!result.applied) {
    console.log('Preview only — no files changed. Re-run the same command with --yes after consent.');
    console.log(`Launcher: ${result.launcherPath}`);
    console.log(result.rcBlock);
  } else {
    console.log(`Launcher installed: ${result.launcherPath}`);
    console.log(`Shell rc updated: ${result.rcPath}`);
    if (result.backupPath) console.log(`Shell rc backup: ${result.backupPath}`);
    console.log('Open a new terminal, or source the rc file and invoke the alias on the next command line.');
  }
} catch (error) {
  console.error(`[thiscode] launcher install failed: ${error.message}`);
  process.exit(2);
}
