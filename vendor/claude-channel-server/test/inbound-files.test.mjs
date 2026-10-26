import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { attachmentBlock, downloadFiles, humanSubtypeAllowed, safeName } from '../dist/inbound-files.js';

const TOKEN = 'tkn-bait';

function fakeFetch(routes, seen = []) {
  return async (url, init) => {
    seen.push({ url, auth: init.headers.Authorization });
    const r = routes[url];
    if (r instanceof Error) throw r;
    if (!r) return { ok: false, status: 404, headers: { get: () => null }, arrayBuffer: async () => new ArrayBuffer(0) };
    const body = Buffer.from(r.body ?? '');
    return {
      ok: (r.status ?? 200) < 400,
      status: r.status ?? 200,
      headers: { get: (k) => (k.toLowerCase() === 'content-type' ? r.type ?? 'application/octet-stream' : null) },
      arrayBuffer: async () => body.buffer.slice(body.byteOffset, body.byteOffset + body.length),
    };
  };
}

test('human subtypes: file_share and thread_broadcast pass, edits/joins/bot stay out', () => {
  for (const s of [undefined, 'file_share', 'thread_broadcast']) assert.equal(humanSubtypeAllowed(s), true, String(s));
  for (const s of ['message_changed', 'message_deleted', 'channel_join', 'bot_message']) assert.equal(humanSubtypeAllowed(s), false, s);
});

test('safeName strips path parts and leading dots, keeps extension when truncating', () => {
  const a = safeName('../../etc/passwd');
  assert.ok(!a.includes('/') && !a.startsWith('.'), a);
  assert.equal(safeName(''), 'file');
  assert.equal(safeName(undefined), 'file');
  const long = safeName('가'.repeat(200) + '.pdf');
  assert.ok(long.length <= 120 && long.endsWith('.pdf'), `${long.length}`);
});

test('downloadFiles writes the body 0600 inside dir and sends the bot token as Bearer', async () => {
  const dir = join(mkdtempSync(join(tmpdir(), 'ccs-files-')), 'inbox', 'D1-1.2');
  const seen = [];
  const res = await downloadFiles([{ id: 'F1', name: 'a.zip', size: 5, url_private_download: 'u1' }], TOKEN, dir, fakeFetch({ u1: { body: 'hello' } }, seen));
  assert.equal(res.length, 1);
  assert.ok(res[0].path && res[0].path.startsWith(dir + '/'), res[0].path);
  assert.equal(readFileSync(res[0].path, 'utf8'), 'hello');
  assert.equal(statSync(res[0].path).mode & 0o777, 0o600);
  assert.equal(seen[0].auth, `Bearer ${TOKEN}`);
});

test('downloadFiles turns every failure into a per-file error and never leaks the token', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'ccs-files-'));
  const seen = [];
  const files = [
    { id: 'F403', name: 'x', url_private: 'u403' },
    { id: 'Fhtml', name: 'y', url_private: 'uhtml' },
    { id: 'Fbig', name: 'z', size: 11, url_private: 'ubig' },
    { id: 'Fnone', name: 'w' },
    { id: 'Ftomb', name: 't', mode: 'tombstone', url_private: 'utomb' },
    { id: 'Fthrow', name: 'v', url_private: 'uthrow' },
    { id: 'Fok', name: 'ok.txt', url_private: 'uok' },
  ];
  const res = await downloadFiles(files, TOKEN, dir, fakeFetch({
    u403: { status: 403 },
    uhtml: { type: 'text/html; charset=utf-8', body: '<html>login</html>' },
    uthrow: new Error(`boom ${TOKEN}`),
    uok: { body: 'fine' },
  }, seen), 10);
  const byId = Object.fromEntries(res.map((r) => [r.file.id, r]));
  assert.match(byId.F403.error, /HTTP 403/);
  assert.match(byId.Fhtml.error, /HTML/);
  assert.match(byId.Fbig.error, /too large/);
  assert.match(byId.Fnone.error, /no download url/);
  assert.match(byId.Ftomb.error, /no download url/);
  assert.ok(!byId.Fthrow.error.includes(TOKEN) && byId.Fthrow.error.includes('***'), byId.Fthrow.error);
  assert.ok(byId.Fok.path, 'the good file still lands');
  assert.ok(!seen.some((s) => s.url === 'ubig' || s.url === 'utomb'), 'oversized / tombstone never fetched');
  for (const r of res) assert.ok(!JSON.stringify(r).includes(TOKEN));
});

test('attachmentBlock: empty = "", mixed = count + path + failure line', () => {
  assert.equal(attachmentBlock([]), '');
  const b = attachmentBlock([
    { file: { id: 'F1', name: 'a.zip', size: 2048, mimetype: 'application/zip' }, path: '/s/inbox/D1-1/1-a.zip' },
    { file: { id: 'F2', name: 'b.png', size: 10 }, error: 'HTTP 403' },
  ]);
  assert.ok(b.includes('[첨부 2개'), b);
  assert.ok(b.includes('/s/inbox/D1-1/1-a.zip') && b.includes('2.0KB') && b.includes('application/zip'), b);
  assert.ok(b.includes('내려받기 실패: HTTP 403 · file id F2'), b);
});
