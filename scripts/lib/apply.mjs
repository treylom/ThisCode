// scripts/lib/apply.mjs
import { readFileSync, writeFileSync, copyFileSync, existsSync } from 'node:fs';

export const MARK_START = '<!-- thiscode:rules:start -->';
export const MARK_END = '<!-- thiscode:rules:end -->';

export function backupFile(path) {
  const bak = `${path}.thiscode.bak`;
  if (existsSync(path)) copyFileSync(path, bak);
  return bak;
}

export function injectMarkerBlock(path, body) {
  const block = `${MARK_START}\n${body}\n${MARK_END}`;
  let text = existsSync(path) ? readFileSync(path, 'utf8') : '';
  const re = new RegExp(`${MARK_START}[\\s\\S]*?${MARK_END}`);
  if (re.test(text)) {
    text = text.replace(re, block);
  } else {
    text = text.replace(/\s*$/, '') + `\n\n${block}\n`;
  }
  writeFileSync(path, text);
}
