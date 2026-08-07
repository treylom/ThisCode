// Shared paths, env loading, and logging for both the resident server
// (server.ts) and the per-session MCP stdio proxy (mcp.ts).

import { existsSync, mkdirSync, chmodSync, readFileSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

/**
 * State directory holding the .env, the Unix socket, and the singleton
 * pidfile. Defaults to the same `~/.claude/channels/slack/` convention the
 * `/slack:configure` setup skill already uses, so a fresh checkout only
 * needs the .env dropped in place — no new path to learn.
 */
export const STATE_DIR = process.env.CLAUDE_CHANNEL_SLACK_DIR ?? join(homedir(), '.claude', 'channels', 'slack');
export const ENV_PATH = join(STATE_DIR, '.env');
export const SOCKET_PATH = join(STATE_DIR, 'primary.sock');
export const PID_PATH = join(STATE_DIR, 'primary.pid');

export interface ChannelEnv {
  SLACK_BOT_TOKEN: string;
  SLACK_APP_TOKEN: string;
  ALLOWED_SLACK_USER_ID: string;
  SLACK_CHANNEL_ID: string;
  // (B) bot-interop (2026-08-07) — OPTIONAL and absent by default.
  // Comma-separated U… ids of OTHER bridge bots allowed to speak to this
  // one. Unset/empty = every bot message drops, which is exactly the
  // pre-(B) behavior (fail closed, zero regression for existing installs).
  // Parsing lives in server.ts next to the gate that uses it. There is
  // deliberately no chain-limit knob (2026-08-07 재경님 "빼자" — the ported
  // Discord device is mention-pass + allowlist only; see server.ts).
  ALLOWED_SLACK_BOT_USER_IDS?: string;
}

const REQUIRED_KEYS = ['SLACK_BOT_TOKEN', 'SLACK_APP_TOKEN', 'ALLOWED_SLACK_USER_ID', 'SLACK_CHANNEL_ID'] as const;

export function log(scope: string, message: string): void {
  // stderr only — stdout is the MCP stdio transport in mcp.ts and must stay
  // pure JSON-RPC. server.ts has no such constraint but uses stderr too for
  // one consistent habit across both entry points.
  process.stderr.write(`[${new Date().toISOString()}] [${scope}] ${message}\n`);
}

/**
 * Creates the state directory as 0700 if missing, and tightens it to 0700
 * if it already existed with looser permissions (e.g. created by a stray
 * `mkdir -p` without the mode, or a leftover from before this project
 * existed). This is the code-side half of what the `/slack:configure` skill
 * previously only documented as a one-time manual `chmod 700` — see
 * README.md "Security model" for the audit finding this closes.
 */
export function ensureStateDir(): void {
  mkdirSync(STATE_DIR, { recursive: true, mode: 0o700 });
  chmodSync(STATE_DIR, 0o700);
}

/**
 * Loads and validates the .env file. Never logs or returns anything beyond
 * what the caller explicitly reads off the returned object — callers must
 * not print token values (see README "Token handling").
 */
export function loadEnv(): ChannelEnv {
  if (!existsSync(ENV_PATH)) {
    throw new Error(
      `missing ${ENV_PATH} — copy .env.example there and fill in real values (see README.md "Setup").`,
    );
  }

  const mode = statSync(ENV_PATH).mode & 0o777;
  if (mode !== 0o600) {
    log(
      'config',
      `WARN ${ENV_PATH} has mode ${mode.toString(8)}, expected 0600 (secrets may be group/world-readable). ` +
        `Fix with: chmod 600 ${ENV_PATH}`,
    );
  }

  const raw = readFileSync(ENV_PATH, 'utf8');
  const values: Record<string, string> = {};
  for (const rawLine of raw.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }

  const missing = REQUIRED_KEYS.filter((key) => !values[key]);
  if (missing.length > 0) {
    throw new Error(`${ENV_PATH} is missing required key(s): ${missing.join(', ')}`);
  }

  return values as unknown as ChannelEnv;
}
