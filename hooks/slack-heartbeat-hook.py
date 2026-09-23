#!/usr/bin/env python3
"""slack-heartbeat-hook.py — 10-second "working…" heartbeat for Slack-bridged sessions (PreToolUse + Stop).

Maintainer request (2026-09-23): while a bot is actually working on a Slack message, the
thread shows a "working · Ns" bubble refreshed every 10 s (plus ⏳ on the inbound).
Bot .env resolution: $SLACK_HEARTBEAT_ENV_FILE → $DISCORD_STATE_DIR (discord-<bot> →
~/.claude/channels/slack-<bot>/.env) → ~/.claude/channels/slack/.env.

동작(항상 exit 0 · stdout 비움):
  - 봇 = $DISCORD_STATE_DIR basename 의 discord-<bot> · Slack .env 없으면 무시.
  - transcript 꼬리(256KB)에서 마지막 <channel source="slack…" …> 태그 1개 → 그 뒤에
    mcp__slack-channel__reply tool_use 가 있으면 이미 답한 턴 → 무시. 태그 30분 초과도 무시.
  - PreToolUse: 상태 dir 에 refresh touch · tool 기록 · count +1 · 데몬 없으면 기동.
    reply 도구 호출 자체 = 답 직전 → stop 파일(데몬이 「✔ 처리 끝」 편집 후 종료).
  - Stop: stop 파일.
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import time

TAG_RE = re.compile(r'<channel source="slack[^"]*"([^>]*)>')
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
REPLY_MARK = 'mcp__slack-channel__reply'
STATE_ROOT = pathlib.Path.home() / '.claude-state' / 'slack-heartbeat'
DAEMON = pathlib.Path(__file__).resolve().parent / 'slack_heartbeat_daemon.py'
MAX_AGE_SEC = 30 * 60


def read_tail(path: str, size: int = 262144) -> str:
    with open(path, 'rb') as f:
        f.seek(0, 2)
        end = f.tell()
        f.seek(max(0, end - size))
        return f.read().decode('utf-8', 'replace')


def _texts(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(str(c.get('text', '')) for c in content if isinstance(c, dict) and c.get('type') == 'text')
    return ''


def last_slack_tag(text: str):
    """transcript 꼬리를 «구조»로 읽는다(source-fact §8-3 자기오염 배제): 태그는 user 메시지 본문
    또는 queue-operation enqueue 레코드의 것만 인정 — 내가 도구 입력·결과에 적은 같은 모양 문자열(스펙·코드)은 assistant/tool_result 라 제외.
    뒤에서 앞으로 훑어 첫 태그를 찾고, 그보다 뒤에 reply tool_use 가 있었으면 answered."""
    seen_reply = False
    dequeued = set()  # queue-operation remove = the session actually picked the message up
    for line in reversed(text.splitlines()):
        if not line.startswith('{'):
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        msg = rec.get('message') if isinstance(rec.get('message'), dict) else {}
        role = rec.get('type')
        content = msg.get('content')
        if role == 'assistant' and isinstance(content, list):
            if any(isinstance(c, dict) and c.get('type') == 'tool_use' and c.get('name') == REPLY_MARK for c in content):
                seen_reply = True
            continue
        if role == 'queue-operation' and rec.get('operation') == 'remove':
            dequeued.add(str(rec.get('content') or ''))
            continue
        if role == 'queue-operation' and rec.get('operation') == 'enqueue':
            body = str(rec.get('content') or '')  # 채널 인바운드 = 큐 투입 레코드(2026-09-23 실측)
            if body not in dequeued:
                # 아직 큐에만 있고 세션이 집어 들지 않은 메시지(다른 일 하는 중) → 하트비트 ❌
                # (2026-09-23 재경님: 공지에 무관한 봇 3이 「진행 중」 말풍선을 단 사고)
                continue
        elif role == 'user':
            body = _texts(content)
        else:
            continue
        m = None
        for m in TAG_RE.finditer(body):
            pass
        if not m:
            continue
        attrs = dict(ATTR_RE.findall(m.group(1)))
        if not attrs.get('channel') or not attrs.get('ts'):
            continue
        return attrs['channel'], attrs['ts'], attrs.get('thread_ts') or attrs['ts'], seen_reply
    return None


def resolve_env():
    """(env_path, bot_label) or (None, None)."""
    explicit = os.environ.get('SLACK_HEARTBEAT_ENV_FILE')
    if explicit:
        p = pathlib.Path(explicit).expanduser()
        return (p, p.parent.name) if p.is_file() else (None, None)
    base = os.path.basename(os.environ.get('DISCORD_STATE_DIR', '').rstrip('/'))
    if base.startswith('discord-'):
        bot = base[len('discord-'):]
        p = pathlib.Path.home() / '.claude' / 'channels' / f'slack-{bot}' / '.env'
        return (p, bot) if p.is_file() else (None, None)
    p = pathlib.Path.home() / '.claude' / 'channels' / 'slack' / '.env'
    return (p, 'slack') if p.is_file() else (None, None)


def pid_alive(pidfile: pathlib.Path) -> bool:
    try:
        pid = int(pidfile.read_text().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    event = str(payload.get('hook_event_name') or '')
    env, bot = resolve_env()
    if env is None:
        return
    tp = payload.get('transcript_path')
    if not tp or not os.path.isfile(tp):
        return
    tag = last_slack_tag(read_tail(tp))
    if not tag:
        return
    channel, ts, thread_ts, answered = tag
    try:
        age = time.time() - float(ts)
    except ValueError:
        return
    if age > MAX_AGE_SEC:
        return
    state = STATE_ROOT / bot / f'{channel}-{ts}'
    state.mkdir(parents=True, exist_ok=True)
    tool = str(payload.get('tool_name') or '')
    if event == 'Stop' or tool == REPLY_MARK:
        (state / 'stop').touch()
        return
    if answered or event != 'PreToolUse':
        return
    (state / 'refresh').touch()
    (state / 'tool').write_text(tool)
    cnt = state / 'count'
    try:
        n = int(cnt.read_text().strip() or 0)
    except Exception:
        n = 0
    cnt.write_text(str(n + 1))
    if (state / 'stop').exists():
        return
    if pid_alive(state / 'daemon.pid'):
        return
    with open(state / 'daemon.log', 'ab') as log:
        p = subprocess.Popen(
            [sys.executable, str(DAEMON), str(env), channel, ts, thread_ts, bot],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log,
            start_new_session=True,
        )
    (state / 'daemon.pid').write_text(str(p.pid))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
