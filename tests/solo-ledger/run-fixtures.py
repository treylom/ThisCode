#!/usr/bin/env python3
"""S2 solo ledger fixture harness — P1 fixture-first contract.

Order fixed by meeting 2026-08-12-dispatch-meeting-gate (02-progress 10:51:05):
  ① parent-dir / post-replace EIO + restart
  ② check→writer→claim race (same-lock sequence)
  ③ normal / mismatch / torn CLEAR
  ④ lock identity · orphan claim succession (+ path verification 4종)
(⑤ 연결 probe lives with the dispatch-room gate, not here.)

Every fixture carries paired controls: positives (MUST accept/claim) and
negatives (MUST reject) — a harness that cannot see its decoys fail is not
measuring. Summary prints assertion totals; FAIL 0 alone is not a pass,
the run also requires the expected assertion count to have executed.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

# Windows 기본 stdout/stderr 는 cp1252 — ①~④·미끼 등 비ASCII 출력이
# UnicodeEncodeError(exit 1) 로 죽는다. utf-8 강제 (POSIX 는 무해).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
MODPATH = os.path.join(REPO, "scripts")
sys.path.insert(0, MODPATH)
import solo_ledger as SL  # noqa: E402

PASS, FAIL = [], []
POS_CTRL = [0, 0]   # [ran, expected]  positive decoys (must accept)
NEG_CTRL = [0, 0]   # negative decoys (must reject)


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           (" — " + detail) if (detail and not cond) else ""))


def fresh_env():
    sdir = tempfile.mkdtemp(prefix="solo-fix-")
    os.environ["MEETING_WATCHDOG_STATE_DIR"] = sdir
    SL._process_quarantine.clear()
    SL._fsync = os.fsync
    SL._replace = os.replace
    room_root = os.path.join(sdir, "rooms")
    room = os.path.join(room_root, "2026-08-12-fixture-room")
    os.makedirs(room)
    for base in ("01-spec.md", "02-progress.md", "03-outcome.md"):
        open(os.path.join(room, base), "w").write("# %s\n" % base)
    with open(os.path.join(sdir, "solo-gate.json"), "w") as fh:
        json.dump({"allowed_roots": [room_root]}, fh)
    return sdir, room


def run_recover(sdir, bot, wd, session):
    out = subprocess.run(
        [sys.executable, os.path.join(MODPATH, "solo_ledger.py"),
         "recover", bot, wd, session],
        capture_output=True, text=True,
        env={**os.environ, "MEETING_WATCHDOG_STATE_DIR": sdir})
    return json.loads(out.stdout), out


def alerts(sdir, kind=None):
    p = os.path.join(sdir, "solo-ledger-alerts.jsonl")
    if not os.path.exists(p):
        return []
    rows = [json.loads(l) for l in open(p) if l.strip()]
    return [r for r in rows if kind is None or r["kind"] == kind]


# ---------------------------------------------------------------- fixture ①
def fixture_1_eio_restart():
    print("① parent-dir/post-replace EIO + restart")
    sdir, room = fresh_env()
    path = SL.create_ledger(sdir, "karpathy", "fix1", "sess-A", sdir, room)

    # (a) post-replace dir-fsync EIO → durability_unknown, fence stays
    calls = {"n": 0}
    real_fsync_dir = SL._fsync_dir

    def eio_on_2nd(p):
        calls["n"] += 1
        if calls["n"] == 2:                # 1=fence prepare, 2=post-replace
            raise OSError(5, "Input/output error (injected)")
        return real_fsync_dir(p)

    SL._fsync_dir = eio_on_2nd
    res = SL.update_ledger(path, "sess-A", {"last_flush_iso": "x"}, "sess-A")
    SL._fsync_dir = real_fsync_dir
    check("①a durability_unknown 반환", not res["ok"]
          and "durability_unknown" in res["reason"], str(res))
    check("①a fence 잔존(재시작-영속 표지)",
          os.path.exists(path + ".fence"))
    check("①a 사람 알림 1+", len(alerts(sdir, "durability_unknown")) >= 1)
    res2 = SL.update_ledger(path, "sess-A", {"last_flush_iso": "y"}, "sess-A")
    check("①a 동일 프로세스 후속 행동 0(quarantine)",
          not res2["ok"] and "quarantin" in res2["reason"], str(res2))

    # (b) restart = clean subprocess recovery → claim 0·injection 0·alert 1+
    rec, _ = run_recover(sdir, "karpathy", sdir, "sess-B")
    NEG_CTRL[0] += 1
    check("①b 재시작 후 claim 0", rec["claimed"] == [], str(rec))
    check("①b 재시작 후 injection 0", rec["injections"] == [])
    check("①b 재시작 후 reject+alert", path in rec["rejected"]
          and len(alerts(sdir, "recovery_fence_reject")) >= 1)

    # (c) ㉮ fence 부모-dir EIO (prepare stage 2) → pre-replace 처분
    sdir2, room2 = fresh_env()
    path2 = SL.create_ledger(sdir2, "karpathy", "fix1b", "sess-A", sdir2, room2)
    before = open(path2).read()
    calls2 = {"n": 0}

    def eio_on_1st(p):
        calls2["n"] += 1
        if calls2["n"] == 1:
            raise OSError(5, "Input/output error (injected)")
        return real_fsync_dir(p)

    SL._fsync_dir = eio_on_1st
    res3 = SL.update_ledger(path2, "sess-A", {"last_flush_iso": "z"}, "sess-A")
    SL._fsync_dir = real_fsync_dir
    check("①c fence-prepare 실패 = fail-closed", not res3["ok"])
    check("①c 구 원장 보존(바이트 동일)", open(path2).read() == before)
    rec2, _ = run_recover(sdir2, "karpathy", sdir2, "sess-C")
    NEG_CTRL[0] += 1
    check("①c 잔존 fence → 재시작 거부(safe quarantine)",
          rec2["claimed"] == [] and path2 in rec2["rejected"], str(rec2))


# ---------------------------------------------------------------- fixture ②
def fixture_2_race():
    print("② check→writer→claim race (동일-락 시퀀스)")
    sdir, room = fresh_env()
    path = SL.create_ledger(sdir, "karpathy", "fix2", "sess-A", sdir, room)

    # writer: lock 보유 + fence PREPARE 후 crash(잠금은 exit 때 해제).
    # recovery 가 락 밖 사전검사로 claim 하면 fence_present_at_claim race 재현.
    writer = (
        "import os,sys,fcntl,time,json\n"
        "sys.path.insert(0, %r)\n"
        "import solo_ledger as SL\n"
        "path=%r\n"
        "fd=os.open(path+'.lock', os.O_RDWR|os.O_CREAT)\n"
        "fcntl.flock(fd, fcntl.LOCK_EX)\n"
        "SL._fence_prepare(path, 1, 'race-tx')\n"
        "print('FENCED', flush=True)\n"
        "time.sleep(1.6)\n"          # crash: clear 없이 종료 → 락 자동 해제
    ) % (MODPATH, path)
    proc = subprocess.Popen([sys.executable, "-c", writer],
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "FENCED"
    t0 = time.monotonic()
    rec, _ = run_recover(sdir, "karpathy", sdir, "sess-B")
    waited = time.monotonic() - t0
    proc.wait()
    NEG_CTRL[0] += 1
    check("② recovery 가 락 대기(≥1.2s 블록 실측)", waited >= 1.2,
          "%.2fs" % waited)
    check("② 락 획득 후 fence 발견 → claim 0",
          rec["claimed"] == [] and path in rec["rejected"], str(rec))

    # 양성 대조(미끼): fence 없는 동일 조건은 claim 되어야 한다 —
    # 위 거부가 «recovery 가 원래 아무것도 claim 안 함»이 아님을 증명.
    os.unlink(path + ".fence")
    SL._fsync_dir(sdir)
    rec2, _ = run_recover(sdir, "karpathy", sdir, "sess-B")
    POS_CTRL[0] += 1
    check("② [양성 미끼] fence 해소 후 claim 1", rec2["claimed"] == [path],
          str(rec2))


# ---------------------------------------------------------------- fixture ③
def fixture_3_clear_states():
    print("③ normal / mismatch / torn CLEAR")
    sdir, room = fresh_env()

    # normal: 정상 tx 후 fence 부재 → claim (양성)
    p_norm = SL.create_ledger(sdir, "karpathy", "norm", "sess-A", sdir, room)
    res = SL.update_ledger(p_norm, "sess-A", {"last_flush_iso": "t"}, "sess-A")
    check("③ 정상 tx ok + fence clear", res["ok"]
          and not os.path.exists(p_norm + ".fence"), str(res))
    rec, _ = run_recover(sdir, "karpathy", sdir, "sess-B")
    POS_CTRL[0] += 1
    check("③ [양성 미끼] normal CLEAR → claim", p_norm in rec["claimed"])

    # foreign-target fence: 결박 위반 = 미해제 취급
    sdir2, room2 = fresh_env()
    p_mis = SL.create_ledger(sdir2, "karpathy", "mis", "sess-A", sdir2, room2)
    open(p_mis + ".fence", "w").write(json.dumps(
        {"target": "/tmp/other-ledger.yaml", "generation": 1,
         "txid": "x", "ts": "t"}))
    rec2, _ = run_recover(sdir2, "karpathy", sdir2, "sess-B")
    NEG_CTRL[0] += 1
    check("③ target 결박 위반 → 거부", p_mis in rec2["rejected"]
          and rec2["claimed"] == [], str(rec2))

    # torn fence: truncated json = fail-closed
    sdir3, room3 = fresh_env()
    p_torn = SL.create_ledger(sdir3, "karpathy", "torn", "sess-A", sdir3, room3)
    open(p_torn + ".fence", "w").write('{"target": "/tm')
    rec3, _ = run_recover(sdir3, "karpathy", sdir3, "sess-B")
    NEG_CTRL[0] += 1
    check("③ torn fence → 거부", p_torn in rec3["rejected"]
          and rec3["claimed"] == [])

    # malformed ledger 자체도 fail-closed
    sdir4, _room4 = fresh_env()
    p_bad = os.path.join(sdir4, "solo-karpathy-bad-sess.yaml")
    open(p_bad, "w").write("state: open\ngarbage line without colon key\n")
    rec4, _ = run_recover(sdir4, "karpathy", sdir4, "sess-B")
    NEG_CTRL[0] += 1
    check("③ malformed 원장 → 거부+alert", p_bad in rec4["rejected"]
          and len(alerts(sdir4, "recovery_ledger_malformed")) >= 1)


# ---------------------------------------------------------------- fixture ④
def fixture_4_lock_identity_orphan():
    print("④ lock identity · single-owner claim/takeover · 경로 검증 4종")
    sdir, room = fresh_env()
    path = SL.create_ledger(sdir, "karpathy", "fix4", "sess-A", sdir, room)
    res = SL.update_ledger(path, "sess-A", {"last_flush_iso": "t0"}, "sess-A")
    assert res["ok"], res
    lock_ino_before = os.stat(path + ".lock").st_ino
    # 대조축 재설계(2026-08-12 CI-fix): 구 판은 ledger st_ino 변화를 쟀는데
    # inode 번호는 파일시스템이 즉시 재사용할 수 있어(ubuntu-22.04 CI 실측
    # FAIL) 플랫폼을 시험하는 자였다. 진짜 불변량은 «쓰기가 항상 설계된
    # 교체 시엄(SL._replace)을 지나고 in-place 로 쓰지 않는다» — 시엄 계수로
    # 직접 잰다(교체 원자성 자체는 OS 계약).
    n_replace = [0]
    real_replace = SL._replace

    def _counting_replace(src, dst):
        n_replace[0] += 1
        return real_replace(src, dst)

    SL._replace = _counting_replace
    try:
        for i in range(1, 3):
            res = SL.update_ledger(path, "sess-A",
                                   {"last_flush_iso": "t%d" % i}, "sess-A")
            assert res["ok"], res
    finally:
        SL._replace = real_replace
    lock_ino_after = os.stat(path + ".lock").st_ino
    check("④ lock inode 불변(불교체 — update 2회 뒤 실측)",
          lock_ino_before == lock_ino_after)
    check("④ ledger 쓰기 = 교체 시엄으로만(대조축 — _replace 정확 2회 + 내용 t2)",
          n_replace[0] == 2 and "t2" in open(path).read())

    # claim mismatch = 패자 열람만
    res = SL.update_ledger(path, "sess-WRONG", {"last_flush_iso": "x"},
                           "sess-WRONG")
    NEG_CTRL[0] += 1
    check("④ owner 불일치 = 거부(열람만)", not res["ok"]
          and res["reason"] == "claim mismatch", str(res))

    # 공백 session recovery = fail-closed (87-doc §D — 빈 claim_session 은
    # «미claim» 표지라 "" 가 claim 하면 원장이 임의 세션에 재개방된다)
    rec_b, _ = run_recover(sdir, "karpathy", sdir, "   ")
    NEG_CTRL[0] += 1
    check("④ 공백 session recovery → claim 0·주입 0 + alert(87-doc §D)",
          rec_b["claimed"] == [] and rec_b["injections"] == []
          and len(alerts(sdir, "recovery_blank_session")) >= 1, str(rec_b))

    # 미claim(claim_session 빈칸) open 원장 → 최초 recovery 가 claim
    # (위 공백-거부와 같은 원장 상태 = 거부가 상태를 안 바꿨다는 양성 대조)
    rec, _ = run_recover(sdir, "karpathy", sdir, "sess-NEW")
    POS_CTRL[0] += 1
    check("④ [양성 미끼] 미claim open 원장 최초 claim", rec["claimed"] == [path],
          str(rec))
    fields = SL.parse_fields(open(path).read())
    check("④ owner = claim_session 승계", SL.owner(fields) == "sess-NEW")

    # single-owner (85-doc §D): 기claim open 원장에 두 번째 세션 recovery
    # = foreign 보고·claim 0·injection 0 — «총 claim = 1» 계약
    rec_f, _ = run_recover(sdir, "karpathy", sdir, "sess-X2")
    NEG_CTRL[0] += 1
    check("④ 기claim open 원장 → foreign·claim 0·injection 0(총 claim=1)",
          rec_f["claimed"] == [] and rec_f["injections"] == []
          and len(rec_f.get("foreign", [])) == 1
          and rec_f["foreign"][0]["owner"] == "sess-NEW", str(rec_f))

    # selector 음성 2종 (open 상태에서): 타 bot / 타 wd
    rec3, _ = run_recover(sdir, "otherbot", sdir, "sess-X")
    NEG_CTRL[0] += 1
    check("④ 타 bot → claim 0", rec3["claimed"] == [])
    other_wd = tempfile.mkdtemp(prefix="otherwd-")
    rec4, _ = run_recover(sdir, "karpathy", other_wd, "sess-X")
    NEG_CTRL[0] += 1
    check("④ 타 wd → claim 0", rec4["claimed"] == [])
    shutil.rmtree(other_wd)

    # takeover CAS (85-doc §D / 83-doc orphan 승인 미결의 확정):
    gen_now = SL.parse_fields(open(path).read())["generation"]
    res = SL.takeover(path, "sess-TK", "sess-NEW", "999", "r-x")
    NEG_CTRL[0] += 1
    check("④ takeover generation CAS 불일치 → 거부",
          not res["ok"] and "generation CAS" in res["reason"], str(res))
    res = SL.takeover(path, "sess-TK", "sess-WRONG", gen_now, "r-x")
    NEG_CTRL[0] += 1
    check("④ takeover owner CAS 불일치 → 거부",
          not res["ok"] and "owner CAS" in res["reason"], str(res))
    res = SL.takeover(path, "sess-TK", "sess-NEW", gen_now, "")
    NEG_CTRL[0] += 1
    check("④ takeover receipt 공란 → 거부", not res["ok"], str(res))
    res = SL.takeover(path, "sess-TK", "sess-NEW", gen_now, "   ")
    NEG_CTRL[0] += 1
    check("④ takeover receipt 공백-only → 거부·미영속(87-doc §D strip 게이트)",
          not res["ok"] and "receipt" in res["reason"]
          and SL.parse_fields(open(path).read()).get("takeover_receipt") == "",
          str(res))
    res = SL.takeover(path, "   ", "sess-NEW", gen_now, "r-ok")
    NEG_CTRL[0] += 1
    check("④ takeover session_id 공백 → 거부(claim_session 소거 차단)",
          not res["ok"] and "session" in res["reason"], str(res))
    res = SL.takeover(path, "sess-TK", "sess-NEW", gen_now,
                      "approved-by-op-#123")
    POS_CTRL[0] += 1
    check("④ [양성 미끼] 정합 CAS+receipt takeover 성공", res["ok"], str(res))
    fields = SL.parse_fields(open(path).read())
    check("④ takeover 후 owner 이전 + receipt 영속",
          SL.owner(fields) == "sess-TK"
          and fields.get("takeover_receipt") == "approved-by-op-#123")

    # closed → claim 0
    SL.update_ledger(path, "sess-TK", {"state": "closed"}, "sess-TK")
    rec2, _ = run_recover(sdir, "karpathy", sdir, "sess-X")
    NEG_CTRL[0] += 1
    check("④ state=closed → claim 0", rec2["claimed"] == [])

    # 경로 검증: ⓑ containment 밖 room → claim 은 되나 injection 0
    sdir5, _room5 = fresh_env()
    outside = tempfile.mkdtemp(prefix="outside-room-")
    for base in ("01-spec.md", "02-progress.md", "03-outcome.md"):
        open(os.path.join(outside, base), "w").write("x\n")
    p5 = SL.create_ledger(sdir5, "karpathy", "out", "sess-A", sdir5, outside)
    rec5, _ = run_recover(sdir5, "karpathy", sdir5, "sess-B")
    NEG_CTRL[0] += 1
    check("④ 허용 root 밖(arbitrary-vault 음성) → injection 0",
          rec5["claimed"] == [p5] and rec5["injections"] == [], str(rec5))
    shutil.rmtree(outside)

    # ⓓ 혼합-room (spec 만 다른 room) → 원장 전체 주입 스킵 + alert
    sdir6, room6 = fresh_env()
    room_b = os.path.join(os.path.dirname(room6), "room-b")
    os.makedirs(room_b)
    open(os.path.join(room_b, "01-spec.md"), "w").write("x\n")
    p6 = SL.create_ledger(sdir6, "karpathy", "mix", "sess-A", sdir6, room6)
    fields6 = SL.parse_fields(open(p6).read())
    fields6["spec_path"] = os.path.join(room_b, "01-spec.md")
    open(p6, "w").write(SL.dump_fields(fields6))
    rec6, _ = run_recover(sdir6, "karpathy", sdir6, "sess-B")
    NEG_CTRL[0] += 1
    check("④ ⓓ room 혼합 → 원장 전체 injection 스킵 + alert",
          rec6["injections"] == []
          and len(alerts(sdir6, "ledger_path_binding_failed")) >= 1,
          str(rec6))

    # 양성 대조: 정상 room = injection 4경로 (room+3파일)
    sdir7, room7 = fresh_env()
    p7 = SL.create_ledger(sdir7, "karpathy", "ok", "sess-A", sdir7, room7)
    rec7, _ = run_recover(sdir7, "karpathy", sdir7, "sess-B")
    POS_CTRL[0] += 1
    check("④ [양성 미끼] 정상 원장 injection 4경로",
          rec7["claimed"] == [p7] and len(rec7["injections"]) == 4, str(rec7))

    # O_EXCL: 같은 좌표 재생성 = 거부
    try:
        SL.create_ledger(sdir7, "karpathy", "ok", "sess-A", sdir7, room7)
        check("④ O_EXCL 중복 생성 거부", False, "no exception")
    except FileExistsError:
        NEG_CTRL[0] += 1
        check("④ O_EXCL 중복 생성 거부", True)


def main():
    POS_CTRL[1] = 5   # 기대 양성 미끼 수 (②1 ③1 ④3)
    NEG_CTRL[1] = 20  # 기대 음성 미끼 수 (①2 ②1 ③3 ④14 — 87-doc §D 3종 포함)
    fixture_1_eio_restart()
    fixture_2_race()
    fixture_3_clear_states()
    fixture_4_lock_identity_orphan()
    total = len(PASS) + len(FAIL)
    expected_min = 39
    print("—" * 60)
    print("검사 %d건 실행(기대 ≥%d) · PASS %d · FAIL %d" %
          (total, expected_min, len(PASS), len(FAIL)))
    print("미끼: 양성 %d/%d · 음성 %d/%d" %
          (POS_CTRL[0], POS_CTRL[1], NEG_CTRL[0], NEG_CTRL[1]))
    if FAIL:
        print("FAILED:", FAIL)
        return 1
    if total < expected_min or POS_CTRL[0] != POS_CTRL[1] \
            or NEG_CTRL[0] != NEG_CTRL[1]:
        print("검사 수/미끼 계수가 기대와 다름 — 미실행은 GREEN 이 아니다")
        return 1
    print("ALL GREEN (FAIL 0 + 계수 일치 + exit 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
