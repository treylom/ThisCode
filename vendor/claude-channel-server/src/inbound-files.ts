// Inbound Slack file attachments (2026-09-24, a user report:
// "a DM with a file never reached the bot — fix it at the root").
//
// Slack delivers a human post that carries files as a `message` event with
// `subtype: 'file_share'` (@slack/types FileShareMessageEvent). The human
// sender gate used to drop EVERY subtype to filter edits/joins, so such posts
// vanished silently. `humanSubtypeAllowed` keeps the edit/join filter and lets
// the two subtypes that carry a human-authored body through.
//
// Files are then fetched with the bot token (Slack `url_private*` needs
// `Authorization: Bearer <bot token>` and the files:read scope) into the
// bot's state dir, and the session gets the local paths appended to the text.
// Nothing here throws: every failure becomes a per-file error line so the text
// part of the message is always delivered.

import { chmodSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

export const HUMAN_PASS_SUBTYPES: ReadonlySet<string> = new Set(['file_share', 'thread_broadcast']);

export function humanSubtypeAllowed(subtype?: string): boolean {
  return !subtype || HUMAN_PASS_SUBTYPES.has(subtype);
}

export interface SlackFile {
  id?: string;
  name?: string;
  title?: string;
  mimetype?: string;
  filetype?: string;
  size?: number;
  url_private_download?: string;
  url_private?: string;
  mode?: string;
}

export interface FileResult {
  file: SlackFile;
  path?: string;
  error?: string;
}

export const MAX_FILE_BYTES = 100 * 1024 * 1024;

type FetchLike = (url: string, init: { headers: Record<string, string>; redirect: 'follow' }) => Promise<{
  ok: boolean;
  status: number;
  headers: { get(name: string): string | null };
  arrayBuffer(): Promise<ArrayBuffer>;
}>;

export function safeName(name: string | undefined): string {
  // eslint-disable-next-line no-control-regex
  let s = (name ?? '').replace(/[\/\\\u0000-\u001f\u007f]/g, '_').replace(/^\.+/, '');
  if (!s) return 'file';
  if (s.length > 120) {
    const dot = s.lastIndexOf('.');
    const ext = dot > 0 && s.length - dot <= 16 ? s.slice(dot) : '';
    s = s.slice(0, 120 - ext.length) + ext;
  }
  return s;
}

function humanSize(n: number | undefined): string {
  if (typeof n !== 'number' || !Number.isFinite(n)) return '크기 미상';
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${(n / 1024 / 1024).toFixed(1)}MB`;
}

function scrub(message: string, token: string): string {
  return token ? message.split(token).join('***') : message;
}

export async function downloadFiles(
  files: SlackFile[],
  token: string,
  dir: string,
  fetchImpl: FetchLike = fetch as unknown as FetchLike,
  maxBytes: number = MAX_FILE_BYTES,
): Promise<FileResult[]> {
  const results: FileResult[] = [];
  for (let i = 0; i < files.length; i++) {
    const file = files[i] ?? {};
    try {
      const url = file.url_private_download ?? file.url_private;
      if (!url || file.mode === 'tombstone') {
        results.push({ file, error: 'no download url' });
        continue;
      }
      if (typeof file.size === 'number' && file.size > maxBytes) {
        results.push({ file, error: `too large (${file.size} bytes > ${maxBytes})` });
        continue;
      }
      mkdirSync(dir, { recursive: true, mode: 0o700 });
      const res = await fetchImpl(url, { headers: { Authorization: `Bearer ${token}` }, redirect: 'follow' });
      if (!res.ok) {
        results.push({ file, error: `HTTP ${res.status}` });
        continue;
      }
      const type = res.headers.get('content-type') ?? '';
      if (type.toLowerCase().startsWith('text/html')) {
        results.push({ file, error: 'got HTML instead of file (bot token lacks files:read?)' });
        continue;
      }
      const body = Buffer.from(await res.arrayBuffer());
      if (body.length > maxBytes) {
        results.push({ file, error: `too large (${body.length} bytes > ${maxBytes})` });
        continue;
      }
      const path = join(dir, `${i + 1}-${safeName(file.name ?? file.title ?? file.id)}`);
      writeFileSync(path, body, { mode: 0o600 });
      chmodSync(path, 0o600);
      results.push({ file, path });
    } catch (err) {
      results.push({ file, error: scrub(err instanceof Error ? err.message : String(err), token) });
    }
  }
  return results;
}

export function attachmentBlock(results: FileResult[]): string {
  if (!results.length) return '';
  const lines = results.map((r) => {
    const name = r.file.name ?? r.file.title ?? r.file.id ?? 'file';
    if (r.path) return `- ${name} (${humanSize(r.file.size)}, ${r.file.mimetype || r.file.filetype || '?'}) → ${r.path}`;
    return `- ${name} (${humanSize(r.file.size)}) → 내려받기 실패: ${r.error ?? '?'} · file id ${r.file.id ?? '?'}`;
  });
  return `\n\n[첨부 ${results.length}개 — Slack 서버가 내려받음]\n` + lines.join('\n');
}
