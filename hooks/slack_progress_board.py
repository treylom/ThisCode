#!/usr/bin/env python3
"""slack_progress_board.py — shared "progress board": one Slack thread message that code keeps rewriting.

Maintainer request (2026-09-23): a long-running job gets one thread and one progress-board
message; code rewrites that message at every step (no model tokens spent on the update).

  open   --key K --title "headline" (--text-file F | --from STEPS)   headline post (new thread) + board
  attach --key K --thread TS        (--text-file F | --from STEPS)   board inside an existing thread
  update --key K                    (--text-file F | --from STEPS)   chat.update the same board (no new post)
  sync   --key K --from STEPS [--thread TS] [--title T]              update if the board exists, else attach/open
  step   --from STEPS --name STEP --status ⬜|⏳|✅|❌ [--note ...]     append one step line (for pipelines)

Common: --bot B (default: $SLACK_HEARTBEAT_ENV_FILE's directory name, or $DISCORD_STATE_DIR's
        discord-<B>) -> token from ~/.claude/channels/slack-B/.env (never printed)
        --channel C (default: first SLACK_CHANNEL_ID of that .env) · --state-dir D
        (default ~/.claude-state/slack-board/<B>) · state = D/<key>.json {channel, thread_ts, board_ts}
STEPS source (two line shapes, auto-detected; a later line for the same step wins; order = first seen):
  (a) step file    `[HH:MM] <bot> | ⏳|✅|❌|⬜ | <step name> | <one-line note>`   (written by `step`)
  (b) progress log `[HH:MM:SS ...] <bot> | <status word> | <sentence>` (select lines with --filter <task id>)
--selftest stubs the API and checks rendering plus the mode transitions (no live calls).
"""
import argparse
import json
import os
import pathlib
import re
import sys
import time
import urllib.request

ICON = {'⬜': '⬜', '⏳': '⏳', '✅': '✅', '❌': '❌'}
# Optional status-word mapping for progress-log lines (shape b). These are the words one
# deployment happens to use; edit them for your own language/vocabulary. First match wins.
STATUS_WORDS = [
    (('된', '완료', '영수증', 'PASS', '종결', '수리', 'done', 'complete'), '✅'),
    (('안됨', '차단', '실패', 'FAIL', '거부', 'blocked', 'failed'), '❌'),
    (('대기', '보류', '이월', '미발주', 'waiting', 'deferred'), '⬜'),
]
STEP_RE = re.compile(r'^\[(\d\d:\d\d)(?::\d\d)?(?: [A-Za-z]+)?\]\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*(?:\|\s*(.*))?$')


def bot_name(explicit):
    if explicit:
        return explicit
    env_file = os.environ.get('SLACK_HEARTBEAT_ENV_FILE')
    if env_file:
        return pathlib.Path(env_file).expanduser().parent.name.replace('slack-', '', 1)
    base = os.path.basename(os.environ.get('DISCORD_STATE_DIR', '').rstrip('/'))
    return base[len('discord-'):] if base.startswith('discord-') else None


def read_env(bot):
    env = pathlib.Path.home() / '.claude' / 'channels' / f'slack-{bot}' / '.env'
    out = {}
    for line in env.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class Slack:
    def __init__(self, token):
        self.token = token

    def call(self, method, data):
        req = urllib.request.Request('https://slack.com/api/' + method, data=json.dumps(data).encode(),
                                     headers={'Authorization': 'Bearer ' + self.token,
                                              'Content-Type': 'application/json; charset=utf-8'})
        try:
            return json.load(urllib.request.urlopen(req, timeout=10))
        except Exception as e:  # network
            return {'ok': False, 'error': f'exc:{type(e).__name__}'}


def status_icon(word):
    w = word.strip()
    if w in ICON:
        return w
    for keys, icon in STATUS_WORDS:
        if any(k in w for k in keys):
            return icon
    return '⏳'


def parse_steps(path, flt=None, last=14):
    """-> [(icon, hhmm, name, note)]; the last line for a step wins; order = first appearance."""
    order, latest = [], {}
    for raw in pathlib.Path(path).read_text(encoding='utf-8').splitlines():
        m = STEP_RE.match(raw.strip())
        if not m:
            continue
        hhmm, _bot, status, name, note = m.groups()
        if flt and flt not in raw:
            continue
        if note is None:  # shape (b): the sentence itself is the step name
            name, note = name[:70], ''
        name = name.strip()
        if name not in latest:
            order.append(name)
        latest[name] = (status_icon(status), hhmm, name, (note or '').strip())
    rows = [latest[n] for n in order]
    return rows[-last:] if last else rows


def render(title, rows):
    lines = [f'📊 {title} (updated by code at every step)']
    for icon, hhmm, name, note in rows:
        t = f' {hhmm}' if icon in ('✅', '❌') else ''
        lines.append(f'{icon}{t} {name}' + (f' — {note}' if note else ''))
    done = sum(1 for r in rows if r[0] == '✅')
    lines.append(f'— {done}/{len(rows)} steps · updated {time.strftime("%H:%M")}')
    return '\n'.join(lines)


def run(a, slack, state_dir, default_channel):
    state_dir.mkdir(parents=True, exist_ok=True)
    sf = state_dir / f'{a.key}.json' if a.key else None
    st = json.loads(sf.read_text()) if sf and sf.is_file() else None
    src = a.__dict__['from']

    if a.mode == 'step':
        line = f'[{time.strftime("%H:%M")}] {a.bot or "-"} | {a.status} | {a.name}' + (f' | {a.note}' if a.note else '')
        with open(src, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        print('step', line)
        return 0

    if a.text_file:
        text = pathlib.Path(a.text_file).read_text(encoding='utf-8')
    else:
        text = render(a.title or (st or {}).get('title') or a.key, parse_steps(src, a.filter, a.last))

    mode = a.mode
    if mode == 'sync':
        mode = 'update' if st else ('attach' if a.thread else 'open')
    if mode == 'update':
        if not st:
            print('update: no state file', sf); return 1
        r = slack.call('chat.update', {'channel': st['channel'], 'ts': st['board_ts'], 'text': text})
        print(f"update ok={r.get('ok')} board={st['board_ts']} err={r.get('error')}")
        return 0 if r.get('ok') else 1
    channel = a.channel or default_channel
    if mode == 'open':
        if not a.title:
            print('open: --title is required'); return 2
        head = slack.call('chat.postMessage', {'channel': channel, 'text': a.title})
        if not head.get('ok'):
            print(f"open head ok=False err={head.get('error')}"); return 1
        thread, channel = head['ts'], head['channel']
    else:
        if not a.thread:
            print('attach: --thread is required'); return 2
        thread = a.thread
    r = slack.call('chat.postMessage', {'channel': channel, 'thread_ts': thread, 'text': text})
    if r.get('ok') and sf:
        sf.write_text(json.dumps({'channel': r['channel'], 'thread_ts': thread, 'board_ts': r['ts'],
                                  'title': a.title or a.key}, ensure_ascii=False))
    print(f"{mode} ok={r.get('ok')} thread={thread} board={r.get('ts')} err={r.get('error')}")
    return 0 if r.get('ok') else 1


def selftest():
    import tempfile
    calls = []

    class Stub:
        def call(self, m, d):
            calls.append((m, d.get('text', '')[:40]))
            return {'ok': True, 'ts': f'{len(calls)}.0', 'channel': d.get('channel', 'C1')}

    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d); steps = d / 's.steps'
        steps.write_text('[10:00] bot-a | ✅ | step one\n[10:05] bot-a | ⏳ | step two | 3 items\n'
                         '[10:10] bot-a | ✅ | step two | 0 failures\n[10:10] bot-a | ⬜ | step three\n'
                         '[10:12:00 UTC] bot-b | done | TASK-1 · sentence-shaped line\n', encoding='utf-8')
        rows = parse_steps(steps)
        assert [r[0] for r in rows] == ['✅', '✅', '⬜', '✅'], rows
        assert rows[1][3] == '0 failures', rows[1]
        ns = argparse.Namespace(mode='sync', key='k', title='T', text_file=None, thread=None, channel='D1',
                                filter=None, last=14, bot='stub', status=None, name=None, note=None)
        ns.__dict__['from'] = str(steps)
        assert run(ns, Stub(), d / 'state', 'D1') == 0   # -> open
        assert run(ns, Stub(), d / 'state', 'D1') == 0   # -> update
        seq = [m for m, _ in calls]
        assert seq == ['chat.postMessage', 'chat.postMessage', 'chat.update'], seq
        assert calls[1][1].startswith('📊 T'), calls[1]
    print('selftest PASS', seq)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['open', 'attach', 'update', 'sync', 'step'], nargs='?')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--bot'); ap.add_argument('--key'); ap.add_argument('--title')
    ap.add_argument('--text-file'); ap.add_argument('--from'); ap.add_argument('--filter'); ap.add_argument('--last', type=int, default=14)
    ap.add_argument('--thread'); ap.add_argument('--channel'); ap.add_argument('--state-dir')
    ap.add_argument('--name'); ap.add_argument('--status', choices=list(ICON)); ap.add_argument('--note')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.mode:
        ap.error('a mode is required')
    bot = bot_name(a.bot)
    if not bot:
        print('--bot, SLACK_HEARTBEAT_ENV_FILE or DISCORD_STATE_DIR is required'); return 2
    a.bot = bot
    if a.mode == 'step':
        if not a.__dict__['from'] or not a.name or not a.status:
            ap.error('step needs --from, --name and --status')
        return run(a, None, pathlib.Path(a.state_dir or '/tmp'), None)
    if a.mode != 'update' and not a.text_file and not a.__dict__['from']:
        ap.error('--text-file or --from is required')
    env = read_env(bot)
    state_dir = pathlib.Path(a.state_dir).expanduser() if a.state_dir else pathlib.Path.home() / '.claude-state' / 'slack-board' / bot
    return run(a, Slack(env['SLACK_BOT_TOKEN']), state_dir, env.get('SLACK_CHANNEL_ID', '').split(',')[0])


if __name__ == '__main__':
    sys.exit(main())
