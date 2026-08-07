// Prevents two resident server processes from binding `primary.sock` at
// once. Without this, a second `npm start` would `unlinkSync` the live
// process's socket file out from under it (see server.ts `startIpcServer`)
// and silently split inbound Slack traffic between two processes — a
// footgun worth ~20 lines to close. A plain pidfile + `kill(pid, 0)`
// liveness check is enough here; no flock/native dependency needed.

import { existsSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';
import { PID_PATH } from './config.js';

function isAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return (err as NodeJS.ErrnoException).code !== 'ESRCH';
  }
}

/**
 * Throws if another live instance already holds the pidfile. Otherwise
 * claims it for this process and registers cleanup on exit.
 */
export function acquireSingleton(): void {
  if (existsSync(PID_PATH)) {
    const raw = readFileSync(PID_PATH, 'utf8').trim();
    const pid = Number.parseInt(raw, 10);
    if (Number.isInteger(pid) && pid > 0 && isAlive(pid)) {
      throw new Error(
        `another claude-channel-server is already running (pid ${pid}). ` +
          `Stop it first, or remove ${PID_PATH} if you're sure it's stale.`,
      );
    }
    unlinkSync(PID_PATH); // stale pidfile from a crashed/killed instance
  }

  writeFileSync(PID_PATH, String(process.pid), { mode: 0o600 });

  process.on('exit', () => {
    try {
      if (readFileSync(PID_PATH, 'utf8').trim() === String(process.pid)) {
        unlinkSync(PID_PATH);
      }
    } catch {
      // already gone — nothing to clean up
    }
  });
}
