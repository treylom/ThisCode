#!/usr/bin/env python3
"""slack_heartbeat_daemon.py <env_file> <channel> <inbound_ts> <thread_ts> [bot_label] — 10-second Slack "working" heartbeat.

스펙 46 §2. 스레드에 「⏳ 진행 중 · N초 · 도구 K회 · 마지막 <tool>」 1통 게시 후 10초마다 같은
말풍선을 chat.update 로 갱신. 인바운드에 ⏳(hourglass_flowing_sand) 반응을 붙이고 끝나면 뗀다.
종료 = stop 파일(훅) → 「✔ 처리 끝 · N초 · 도구 K회」 / refresh 300초 stale / API 3회 연속 실패.
의존 0(urllib) · 토큰 값은 절대 출력·로그 ❌.  --selftest = urllib 스텁으로 호출 순서 검증.
"""
import json
import os
import pathlib
import sys
import time
import urllib.request

INTERVAL = 10
PAUSE_AFTER = 60
GIVE_UP_AFTER = 120
STATE_ROOT = pathlib.Path.home() / '.claude-state' / 'slack-heartbeat'


class Slack:
    def __init__(self, token: str):
        self.token = token
        self.fail = 0

    def call(self, method: str, data: dict) -> dict:
        req = urllib.request.Request(
            'https://slack.com/api/' + method, data=json.dumps(data).encode(),
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json; charset=utf-8'})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=8))
        except Exception as e:  # network
            r = {'ok': False, 'error': f'exc:{type(e).__name__}'}
        self.fail = 0 if r.get('ok') else self.fail + 1
        return r


def read_token(env_file: str) -> str:
    for line in pathlib.Path(env_file).expanduser().read_text().splitlines():
        if line.startswith('SLACK_BOT_TOKEN='):
            return line.split('=', 1)[1].strip().strip('"')
    raise SystemExit('no SLACK_BOT_TOKEN')


def run(bot: str, channel: str, inbound_ts: str, thread_ts: str, slack: Slack, state: pathlib.Path,
        sleep=time.sleep, clock=time.time) -> int:
    started = clock()
    log = open(state / 'daemon.log', 'a')

    def note(msg: str) -> None:
        log.write(f'{time.strftime("%H:%M:%S")} {msg}\n'); log.flush()

    def counts():
        try:
            k = int((state / 'count').read_text().strip() or 0)
        except Exception:
            k = 0
        try:
            tool = (state / 'tool').read_text().strip()
        except Exception:
            tool = '-'
        return k, tool

    slack.call('reactions.add', {'channel': channel, 'timestamp': inbound_ts, 'name': 'hourglass_flowing_sand'})
    r = slack.call('chat.postMessage', {'channel': channel, 'thread_ts': thread_ts, 'text': '⏳ working · 0s · 0 tool calls'})
    if not r.get('ok'):
        note(f'post failed {r.get("error")}'); return 1
    msg_ts = r['ts']
    note(f'started msg={msg_ts}')
    while True:
        sleep(INTERVAL)
        n = int(clock() - started)
        k, tool = counts()
        try:
            stale = clock() - (state / 'refresh').stat().st_mtime
        except Exception:
            stale = GIVE_UP_AFTER + 1
        stop = (state / 'stop').exists()
        if stop or stale > GIVE_UP_AFTER:
            why = '' if stop else ' (no tool call for 2 min)'
            slack.call('chat.update', {'channel': channel, 'ts': msg_ts, 'text': f'✔ done{why} · {n}s · {k} tool calls'})
            slack.call('reactions.remove', {'channel': channel, 'timestamp': inbound_ts, 'name': 'hourglass_flowing_sand'})
            note(f'done n={n} k={k} stop={stop}'); return 0
        if stale > PAUSE_AFTER:
            text = f'⏸ no tool call for {int(stale)}s · {n}s · {k} tool calls'
        else:
            text = f'⏳ working · {n}s · {k} tool calls · last {tool}'
        slack.call('chat.update', {'channel': channel, 'ts': msg_ts, 'text': text})
        if slack.fail >= 3:
            note('3 consecutive api failures — exit'); return 2


def selftest() -> int:
    import tempfile
    calls = []

    class Stub(Slack):
        def __init__(self):
            super().__init__('stub')

        def call(self, method, data):
            calls.append((method, data.get('text') or data.get('name')))
            return {'ok': True, 'ts': '1.000'}

    with tempfile.TemporaryDirectory() as d:
        st = pathlib.Path(d)
        (st / 'refresh').touch(); (st / 'count').write_text('3'); (st / 'tool').write_text('Bash')
        ticks = {'n': 0}
        t0 = time.time()

        def fake_sleep(_):
            ticks['n'] += 1
            (st / 'refresh').touch()
            if ticks['n'] == 3:
                (st / 'stop').touch()

        rc = run('stub', 'D1', '10.1', '10.1', Stub(), st, sleep=fake_sleep, clock=lambda: t0 + ticks['n'] * 10)
    seq = [m for m, _ in calls]
    want = ['reactions.add', 'chat.postMessage', 'chat.update', 'chat.update', 'chat.update', 'reactions.remove']
    ok = rc == 0 and seq == want and calls[-2][1].startswith('✔ done') and calls[2][1].startswith('⏳ working · 10s · 3 tool calls')
    print('selftest', 'PASS' if ok else 'FAIL', seq, calls[-2][1])
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == '--selftest':
        return selftest()
    if len(sys.argv) not in (5, 6):
        print(__doc__); return 2
    env_file, channel, inbound_ts, thread_ts = sys.argv[1:5]
    bot = sys.argv[5] if len(sys.argv) == 6 else pathlib.Path(env_file).expanduser().parent.name
    state = STATE_ROOT / bot / f'{channel}-{inbound_ts}'
    state.mkdir(parents=True, exist_ok=True)
    return run(bot, channel, inbound_ts, thread_ts, Slack(read_token(env_file)), state)


if __name__ == '__main__':
    sys.exit(main())
