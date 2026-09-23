#!/usr/bin/env python3
"""slack-heartbeat-hook.py — 10-second "working…" heartbeat for Slack-bridged sessions (PreToolUse + Stop).

Maintainer request (2026-09-23): while a bot is actually working on a Slack message, the
thread shows a "working · Ns" bubble refreshed every 10 s (plus ⏳ on the inbound).
Bot .env resolution: $SLACK_HEARTBEAT_ENV_FILE → $DISCORD_STATE_DIR (discord-<bot> →
~/.claude/channels/slack-<bot>/.env) → ~/.claude/channels/slack/.env.

Behaviour (always exits 0, prints nothing):
  - No Slack .env for this bot -> do nothing.
  - Read the transcript tail (256KB) for the last <channel source="slack..."> tag; if a
    mcp__slack-channel__reply tool_use follows it the turn is already answered -> do nothing.
    Tags older than 30 minutes are ignored.
  - PreToolUse: touch `refresh`, record the tool name, bump `count`, start the daemon if
    none is alive. A call to the reply tool itself means the answer is about to be posted
    -> write `stop` (the daemon edits the bubble to "done" and exits).
  - Stop: write `stop`.
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
    """Read the transcript tail structurally: only a tag inside a user message or a
    queue-operation enqueue record counts (the same text inside tool input/results is the
    bot quoting itself). Scan backwards; if a reply tool_use came after the tag, it is answered."""
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
            body = str(rec.get('content') or '')  # a channel inbound arrives as a queue record
            if body not in dequeued:
                # Still queued, not picked up by the session (it is busy with something
                # else) -> no heartbeat. Otherwise a broadcast makes every busy bot post
                # a "working" bubble on a message it is not actually handling.
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
