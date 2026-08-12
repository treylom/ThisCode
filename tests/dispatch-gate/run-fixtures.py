#!/usr/bin/env python3
"""Gate A (dispatch-room-gate) fixture harness — P1 fixture ⑤ + D5 origin.

체크리스트 선두(코난 이월): origin_reclassified denial 로그 — 위조 origin 이
통과 티켓이 되지 않고, 재분류 사실이 로그에 남는지가 첫 검사다.
양성(발화해야 함)·음성(안 해야 함) 미끼 쌍 + 계수 기대값 대조로 판정.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
GATE = os.path.join(REPO, "hooks", "dispatch-room-gate.py")

PASS, FAIL = [], []
POS_CTRL = [0, 0]
NEG_CTRL = [0, 0]

TOP = "111111111111111111"
BOT_ID = "222222222222222222"


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           (" — " + detail) if (detail and not cond) else ""))


def setup(with_config=True, with_roster=True):
    sdir = tempfile.mkdtemp(prefix="gate-fix-")
    roster = os.path.join(sdir, "bot-roster.yaml")
    if with_roster:
        open(roster, "w").write('bots:\n  konan:\n    user_id: "%s"\n' % BOT_ID)
    if with_config:
        with open(os.path.join(sdir, "dispatch-gate.json"), "w") as fh:
            json.dump({"top_channels": [TOP], "roster_path": roster}, fh)
    return sdir


def run_gate(sdir, payload, extra_env=None):
    env = {**os.environ, "MEETING_WATCHDOG_STATE_DIR": sdir}
    if extra_env:
        env.update(extra_env)
    out = subprocess.run([sys.executable, GATE], input=json.dumps(payload),
                        capture_output=True, text=True, env=env)
    denied = "permissionDecision" in out.stdout and '"deny"' in out.stdout
    return denied, out


def denials(sdir):
    p = os.path.join(sdir, "dispatch-gate-denials.jsonl")
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p) if l.strip()]


def payload(chat_id=TOP, text=None, tool="mcp__plugin_discord_discord__reply",
            origin=None):
    ti = {"chat_id": chat_id,
          "text": text if text is not None else "<@%s> 작업 착수" % BOT_ID}
    if origin is not None:
        ti["origin"] = origin
    return {"tool_name": tool, "tool_input": ti}


def main():
    print("⑤-0 origin_reclassified denial 로그 (체크리스트 선두)")
    sdir = setup()
    denied, _ = run_gate(sdir, payload(origin="bridge_notice"))
    POS_CTRL[0] += 1
    rows = denials(sdir)
    check("0 위조 origin=bridge_notice → deny(통과 티켓 아님)", denied)
    check("0 denial 로그 origin_reclassified=true",
          len(rows) == 1 and rows[0].get("origin_reclassified") is True
          and rows[0].get("origin_effective") == "model"
          and rows[0].get("origin_claimed") == "bridge_notice",
          str(rows))

    print("⑤-1 기본 차단·통과 축")
    sdir = setup()
    denied, _ = run_gate(sdir, payload())
    POS_CTRL[0] += 1
    check("1 top+봇멘션+마커 → deny(양성)", denied)
    rows = denials(sdir)
    check("1 denial 로그 1행·origin_claimed 부재(reclassify false)",
          len(rows) == 1 and rows[0].get("origin_reclassified") is False)

    denied, out = run_gate(sdir, payload(chat_id="333333333333333333"))
    NEG_CTRL[0] += 1
    check("2 비-top(스레드) → pass(음성 미끼)", not denied and out.stdout == "")

    denied, _ = run_gate(sdir, payload(text="[공지] <@%s> 작업 재개" % BOT_ID))
    NEG_CTRL[0] += 1
    check("3 carve-out 태그 → pass", not denied)

    denied, _ = run_gate(sdir, payload(text="봇 없이 작업 이야기만"))
    NEG_CTRL[0] += 1
    check("4 멘션 없음 → pass", not denied)

    denied, _ = run_gate(sdir, payload(tool="Bash"))
    NEG_CTRL[0] += 1
    check("5 비대상 도구(bridge 직접발신 구조 음성, D5) → pass", not denied)

    print("⑤-2 fail-closed 축")
    sdir = setup(with_roster=False)
    denied, _ = run_gate(sdir, payload(text="<@999888777> 작업 착수"))
    POS_CTRL[0] += 1
    rows = denials(sdir)
    check("6 로스터 미독 → 멘션 동반 발주 deny(fail-closed)",
          denied and rows and rows[-1].get("roster_fail_closed") is True)

    sdir = setup(with_config=False)
    denied, _ = run_gate(sdir, payload())
    NEG_CTRL[0] += 1
    check("7 config 부재 → 게이트 비활성 pass(설치층이 잡음)", not denied)

    print("⑤-3 연결 probe (D2 — 0번 칸)")
    # wired settings 합성
    wired = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"hooks": {"PreToolUse": [{"matcher": "mcp__plugin_discord",
               "hooks": [{"type": "command",
                          "command": "python3 %s" % GATE}]}]}}, wired)
    wired.close()
    sdir = setup()
    out = subprocess.run([sys.executable, GATE, "--probe"],
                        capture_output=True, text=True,
                        env={**os.environ, "MEETING_WATCHDOG_STATE_DIR": sdir,
                             "DISPATCH_GATE_SETTINGS": wired.name})
    POS_CTRL[0] += 1
    check("8 probe 4/4 PASS(wiring·config·deny·pass)",
          out.returncode == 0 and "PROBE PASS 4/4" in out.stdout, out.stdout)

    unwired = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"hooks": {}}, unwired)
    unwired.close()
    out = subprocess.run([sys.executable, GATE, "--probe"],
                        capture_output=True, text=True,
                        env={**os.environ, "MEETING_WATCHDOG_STATE_DIR": sdir,
                             "DISPATCH_GATE_SETTINGS": unwired.name})
    NEG_CTRL[0] += 1
    check("9 미배선 settings → probe FAIL(음성 미끼)",
          out.returncode == 1 and "wiring" in out.stdout, out.stdout)

    sdir = setup(with_config=False)
    out = subprocess.run([sys.executable, GATE, "--probe"],
                        capture_output=True, text=True,
                        env={**os.environ, "MEETING_WATCHDOG_STATE_DIR": sdir,
                             "DISPATCH_GATE_SETTINGS": wired.name})
    NEG_CTRL[0] += 1
    check("10 config 부재 → probe FAIL(«비활성=완료» 차단)",
          out.returncode == 1, out.stdout)
    os.unlink(wired.name)
    os.unlink(unwired.name)

    total = len(PASS) + len(FAIL)
    POS_CTRL[1], NEG_CTRL[1] = 4, 7
    expected_min = 13
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
