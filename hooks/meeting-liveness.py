#!/usr/bin/env python3
"""meeting-liveness.py — B1 (flagship): 회의 active 봇 per-bot liveness 강제 push.

04-synthesis B1 (maintainer seed). 회의 02-progress.md 의 각 active 봇 마지막 append 시각이
임계(기본 180s)를 넘으면 그 봇을 @mention 으로 재구동 push (soft beat → hard push).

⚠️ 기본 = DRY-RUN (대상만 출력, 발신 안 함). 실제 발신 = --send.
   launchd 자동 실행 활성화 + meeting_watchdog.py 통합 = 스트레인지 도메인(아침 승인).
   본 스크립트는 검증된 standalone 모듈만 제공하며 라이브 meeting_watchdog.py 를 수정하지 않는다.
   (무인 중 라이브 시스템 스크립트 수정·실발신 회피 — carve-out.)

stdlib only. 시각 = KST. 02-progress 의 '[HH:MM KST] <bot> | ...' 라인 파싱.
"""
import argparse, json, os, re, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
DISCORD_API = "https://discord.com/api/v10"
LINE = re.compile(r"^\[(\d{2}):(\d{2})\s*KST\]\s*([^\s|]+)\s*\|")


def last_append_per_bot(progress_path):
    """02-progress.md → {bot: datetime(KST)} 각 봇 마지막 append. 파일 순서=시간 순서 가정."""
    out = {}
    try:
        lines = open(progress_path, encoding="utf-8").read().splitlines()
    except OSError:
        return out
    now = datetime.now(KST)
    for ln in lines:
        m = LINE.match(ln.strip().lstrip("- "))
        if not m:
            continue
        hh, mm, bot = int(m.group(1)), int(m.group(2)), m.group(3)
        dt = datetime(now.year, now.month, now.day, hh, mm, tzinfo=KST)
        if dt > now + timedelta(minutes=2):     # 미래 시각 = 자정 넘은 어제 것
            dt -= timedelta(days=1)
        out[bot] = dt
    return out


def silent_bots(progress_path, participants, threshold):
    """participants={bot:user_id}. 마지막 append age>threshold(초) 또는 기록無 인 봇."""
    last = last_append_per_bot(progress_path)
    now = datetime.now(KST)
    res = []
    for bot, uid in participants.items():
        dt = last.get(bot)
        age = (now - dt).total_seconds() if dt else None
        if age is None or age > threshold:
            res.append((bot, uid, int(age) if age is not None else None))
    return res


def _state_dir():
    return os.environ.get("MEETING_WATCHDOG_STATE_DIR",
                          os.path.join(os.path.expanduser("~"), ".claude-state"))


def meeting_active(thread_id):
    """watchdog manifest status==active 인지. 불명확(absent/parse 실패)하면 False.
    ⚠️ sender 는 fail-SAFE = 발신 안 함(False) — watchdog 의 fail-closed=keep-active 와 반대.
    종료/미상 회의에 push 해서 스팸 내는 것을 차단."""
    path = os.path.join(_state_dir(), f"meeting-watchdog-{thread_id}.yaml")
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln.startswith("status:"):
                return ln.split(":", 1)[1].strip() == "active"
    except OSError:
        return False
    return False


def meeting_blocked(thread_id):
    """watchdog manifest 에 blocked_on 이 set 인가. set = 사용자/구현 게이트 대기
    (pause) → 참여봇 침묵 = done-and-waiting 정상(stuck 아님) → active-push skip.
    수동 active-push 도 blocked_on SoT 존중 (자동 stall-mention 과 동일 SoT →
    양-데몬 정합). meeting-protocol.md §3 carve-out."""
    path = os.path.join(_state_dir(), f"meeting-watchdog-{thread_id}.yaml")
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln.startswith("blocked_on:"):
                v = ln.split(":", 1)[1].strip()
                if " #" in v:                  # inline comment strip (flat YAML)
                    v = v.split(" #", 1)[0].strip()
                v = v.lower()
                return bool(v) and v not in ("null", "none", "-")
    except OSError:
        return False
    return False


def done_participants(thread_id):
    """watchdog manifest 의 optional `done_participants:` 필드 → 완결 봇 이름 set.
    개별 봇이 트랙을 완결하고 done-waiting 인데 다른 봇은 아직 active producer라
    meeting-level blocked_on(전체 suppress)을 못 거는 경우, 그 봇만 per-bot probe 에서
    제외한다. meeting_blocked(전체)와 직교 — active producer 는 계속 push, 완결 봇만 skip.
    gate-release 이벤트 전달은 안 막고 liveness nag 만 끈다. 필드 부재/빈값 → 빈 set
    (하위호환). meeting-protocol.md §3 done-waiting carve-out 의 per-bot 판."""
    path = os.path.join(_state_dir(), f"meeting-watchdog-{thread_id}.yaml")
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln.startswith("done_participants:"):
                v = ln.split(":", 1)[1].strip()
                if " #" in v:                      # 인라인 주석 제거
                    v = v.split(" #", 1)[0].strip()
                if not v or v.lower() in ("null", "none", "-", "[]"):
                    return set()
                return {p.split(":")[0].strip().lower()
                        for p in v.strip("[]").split(",") if p.strip()}
    except OSError:
        return set()
    return set()


def _rate_path(thread_id, bot):
    d = os.path.join(_state_dir(), "liveness-rate")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return os.path.join(d, f"{thread_id}-{bot}.ts")


def recently_pinged(thread_id, bot, cooldown):
    """쿨다운 내 이미 ping 했으면 True → 재-ping skip (ticker 마다 같은 봇 재핑=스팸 차단)."""
    try:
        last = float(open(_rate_path(thread_id, bot)).read().strip())
        return (time.time() - last) < cooldown
    except (OSError, ValueError):
        return False


def mark_pinged(thread_id, bot):
    try:
        open(_rate_path(thread_id, bot), "w").write(str(time.time()))
    except OSError:
        pass


def discord_push(thread_id, text, mention_ids):
    """best-effort. 봇 토큰 = MEETING_WATCHDOG_BOT_ENV 또는 DISCORD_STATE_DIR/.env."""
    env = os.environ.get("MEETING_WATCHDOG_BOT_ENV") or (
        os.path.join(os.environ["DISCORD_STATE_DIR"], ".env")
        if os.environ.get("DISCORD_STATE_DIR") else "")
    tok = None
    try:
        for ln in open(env, encoding="utf-8"):
            if ln.strip().startswith("DISCORD_BOT_TOKEN="):
                tok = ln.split("=", 1)[1].strip().strip('"').strip("'")
                break
    except OSError:
        return False
    if not tok:
        return False
    body = json.dumps({"content": text[:1900],
                       "allowed_mentions": {"users": mention_ids}}).encode()
    req = urllib.request.Request(
        f"{DISCORD_API}/channels/{thread_id}/messages", data=body, method="POST",
        headers={"Authorization": f"Bot {tok}", "Content-Type": "application/json",
                 "User-Agent": "meeting-liveness/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (200, 201)
    except (urllib.error.URLError, OSError):
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="회의 per-bot liveness 강제 push (B1)")
    ap.add_argument("--progress", required=True, help="02-progress.md 경로")
    ap.add_argument("--thread-id", required=True)
    ap.add_argument("--participants", required=True, help="bot:user_id,bot:user_id ...")
    ap.add_argument("--threshold", type=int, default=180)
    ap.add_argument("--send", action="store_true", help="실제 발신 (기본 = dry-run)")
    ap.add_argument("--active-only", action="store_true", help="watchdog status=active 회의만 처리 (ticker 안전)")
    ap.add_argument("--cooldown", type=int, default=600, help="per-bot 재-ping 쿨다운 초 (기본 600 = 10분)")
    a = ap.parse_args(argv)
    if a.active_only and not meeting_active(a.thread_id):
        print(f"[{'SEND' if a.send else 'DRY-RUN'}] 회의 비활성(status != active) → skip (thread {a.thread_id})")
        return 0
    if meeting_blocked(a.thread_id):
        print(f"[{'SEND' if a.send else 'DRY-RUN'}] 회의 blocked_on set(done-waiting) → active-push skip (thread {a.thread_id})")
        return 0
    parts = {}
    for pair in a.participants.split(","):
        pair = pair.strip()
        if ":" in pair:
            b, u = pair.split(":", 1)
            if b.strip() and u.strip():
                parts[b.strip()] = u.strip()
    # per-bot done suppression: 완결 봇은 probe 대상 제외 (meeting_blocked 전체
    # suppress 와 직교 — active producer 는 계속 push). meeting-protocol §3.
    done = done_participants(a.thread_id)
    if done:
        suppressed = [b for b in parts if b.lower() in done]
        for b in suppressed:
            parts.pop(b, None)
        if suppressed:
            print(f"[{'SEND' if a.send else 'DRY-RUN'}] done_participants probe skip: "
                  f"{','.join(suppressed)} (thread {a.thread_id})")
    silent = silent_bots(a.progress, parts, a.threshold)
    mode = "SEND" if a.send else "DRY-RUN"
    if not silent:
        print(f"[{mode}] liveness OK — 침묵 봇 없음 (threshold={a.threshold}s, "
              f"participants={len(parts)})")
        return 0
    for bot, uid, age in silent:
        agestr = f"{age}s" if age is not None else "기록없음"
        msg = (f"<@{uid}> [watchdog liveness] {bot} {agestr} 침묵 "
               f"(>{a.threshold}s) — 진행 1줄 보고 부탁합니다. idle 이면 재구동하세요.")
        if a.send:
            if recently_pinged(a.thread_id, bot, a.cooldown):
                print(f"[SEND] SKIP rate-limit(<{a.cooldown}s): {bot} ({uid})")
                continue
            ok = discord_push(a.thread_id, msg, [uid])
            if ok:
                mark_pinged(a.thread_id, bot)
            print(f"[SEND] {'OK' if ok else 'FAIL'}: {bot} ({uid}) age={agestr}")
        else:
            print(f"[DRY-RUN] would push → {bot} ({uid}) age={agestr}")
            print(f"          msg: {msg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
