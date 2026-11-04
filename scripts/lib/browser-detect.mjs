// scripts/lib/browser-detect.mjs
// Browser auto-detect — pick the browser ThisCode drives for web work (Discord portal, Slack app pages …).
//
// Order (first one that is installed AND answers wins):
//   1. ego lite — `ego-browser` CLI (`ego-browser skill` prints a guide ending in "end of guide")
//   2. Aside    — `aside` CLI (`aside --version` exits 0)
//   3. fallback — the existing path (a connected browser-automation MCP, else the Playwright MCP install step)
//
// The user does not configure anything. The absolute path is returned so the command works even when
// the CLI's folder (~/.local/bin) is not on PATH. Probes have a timeout so a stuck CLI never stalls setup.
// Windows: PATH lookup only (whichSync adds .exe/.cmd) — the fixed folders below are macOS/Linux.
import { existsSync, statSync, accessSync, constants } from 'node:fs';
import { join, resolve } from 'node:path';
import { homedir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { whichSync } from './detect.mjs';

export const ORDER = ['ego', 'aside'];

export const CANDIDATES = {
  ego: {
    names: ['ego-browser'],
    paths: ['.local/bin/ego-browser', '.local/share/ego/active_version_dir/Helpers/ego-browser'],
  },
  aside: {
    names: ['aside'],
    paths: ['.local/bin/aside', '.aside/cli/Aside CLI.app/Contents/MacOS/aside', '.aside/bin/aside'],
  },
};

function isExecFile(p) {
  try {
    if (!existsSync(p) || !statSync(p).isFile()) return false;
    accessSync(p, constants.X_OK);
    return true;
  } catch { return false; }
}

export function findBin(kind, { env = process.env, home = homedir() } = {}) {
  const spec = CANDIDATES[kind];
  for (const name of spec.names) {
    const hit = whichSync(name, env);
    if (hit && isExecFile(hit)) return resolve(hit);
  }
  for (const rel of spec.paths) {
    const cand = join(home, rel);
    if (isExecFile(cand)) return resolve(cand);
  }
  return null;
}

export function probe(kind, bin, { timeoutMs = 15000, env = process.env } = {}) {
  const args = kind === 'ego' ? ['skill'] : ['--version'];
  const r = spawnSync(bin, args, { encoding: 'utf8', timeout: timeoutMs, env, stdio: ['ignore', 'pipe', 'pipe'] });
  if (r.error) {
    return { ready: false, why: r.error.code === 'ETIMEDOUT' ? 'probe timeout' : `probe failed: ${r.error.code || 'error'}` };
  }
  if (r.status !== 0) return { ready: false, why: `probe exit ${r.status}` };
  if (kind === 'ego' && !(r.stdout || '').includes('end of guide')) return { ready: false, why: 'guide incomplete' };
  return { ready: true, why: 'ok' };
}

// prefer = "ego" | "aside" → tried first when detected; anything else → auto order.
export function detectBrowser({ env = process.env, home = homedir(), prefer = 'auto', doProbe = true, timeoutMs } = {}) {
  const t = Number(timeoutMs ?? env.THISCODE_BROWSER_PROBE_TIMEOUT_MS ?? 15000) || 15000;
  const detected = {};
  for (const kind of ORDER) {
    const bin = findBin(kind, { env, home });
    let st = { ready: false, why: 'not installed' };
    if (bin) st = doProbe ? probe(kind, bin, { timeoutMs: t, env }) : { ready: true, why: 'not probed' };
    detected[kind] = { found: Boolean(bin), bin, ...st };
  }
  const p = String(prefer || 'auto').toLowerCase();
  const order = ORDER.includes(p) ? [p, ...ORDER.filter((k) => k !== p)] : [...ORDER];
  let provider = 'fallback';
  let reason = 'no ego lite / Aside answered';
  for (const kind of order) {
    if (detected[kind].ready) {
      provider = kind;
      reason = (kind === p ? 'preferred ' : 'auto: ') + kind;
      break;
    }
  }
  return { provider, bin: detected[provider]?.bin ?? null, reason, prefer: p, order: ['ego', 'aside', 'fallback'], detected };
}
