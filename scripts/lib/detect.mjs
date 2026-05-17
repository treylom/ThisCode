// scripts/lib/detect.mjs
import { platform } from 'node:os';
import { existsSync, readFileSync } from 'node:fs';
import { join, delimiter } from 'node:path';

export function detectOS() {
  const p = platform();
  if (p === 'win32') return 'win';
  if (p === 'darwin') return 'mac';
  if (p === 'linux') {
    try {
      if (/microsoft/i.test(readFileSync('/proc/version', 'utf8'))) return 'wsl';
    } catch { /* not WSL */ }
    return 'linux';
  }
  return 'linux';
}

export function whichSync(bin, env = process.env) {
  const exts = process.platform === 'win32' ? ['.exe', '.cmd', ''] : [''];
  for (const dir of (env.PATH || '').split(delimiter)) {
    if (!dir) continue;
    for (const ext of exts) {
      const cand = join(dir, bin + ext);
      if (existsSync(cand)) return cand;
    }
  }
  return null;
}

export function autodiscoverVault(env = process.env) {
  const home = env.CLAUDE_DISCODE_VAULT || env.HOME || env.USERPROFILE || '';
  if (env.CLAUDE_DISCODE_VAULT && existsSync(env.CLAUDE_DISCODE_VAULT)) return env.CLAUDE_DISCODE_VAULT;
  for (const c of ['Documents/Obsidian', 'Documents/Second_Brain', 'obsidian-ai-vault']) {
    const full = join(home, c);
    if (home && existsSync(full)) return full;
  }
  return null;
}

export function detectEnv(env = process.env) {
  return {
    os: detectOS(),
    node: process.versions.node,
    tools: {
      git: !!whichSync('git', env),
      codex: !!whichSync('codex', env),
      claude: !!whichSync('claude', env),
      tmux: !!whichSync('tmux', env),
      python: !!whichSync('python3', env),
    },
    vault: autodiscoverVault(env),
  };
}
