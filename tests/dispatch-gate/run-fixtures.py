#!/usr/bin/env python3
"""Gate A (dispatch-room-gate) fixture harness — P1 fixture ⑤ + D5 origin
+ D2 cwd guard (85-doc 차단 1 수리) + carve-out 관측 계약 (코난 관측 ①).

체크리스트 선두(코난 이월): origin_reclassified denial 로그.
carve-out 계약 명시: «모델 자칭 태그 + 봇멘션 + 발주 마커 = pass 가 계약»
(감사 가능 경로 — fail-closed 승격은 §1.2 프로토콜 폐지와 등가) — 단 그
조합은 관측 로그 1행(pass 유지). cwd 가드: in-cwd 양성 / out-cwd 음성 /
cwd 부재 = $PWD fallback 양·음성.
양성(발화해야 함)·음성(안 해야 함) 미끼 쌍 + 계수 기대값 대조로 판정.
"""

import json
import os
import subprocess
import sys
import tempfile

# Windows 기본 stdout/stderr 는 cp1252 — ⑤·미끼 등 비ASCII 출력이
# UnicodeEncodeError(exit 1) 로 죽는다. utf-8 강제 (POSIX 는 무해).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass

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


def setup(with_config=True, with_roster=True, with_roots=True):
    sdir = tempfile.mkdtemp(prefix="gate-fix-")
    workspace = os.path.join(sdir, "workspace")
    os.makedirs(workspace)
    roster = os.path.join(sdir, "bot-roster.yaml")
    if with_roster:
        open(roster, "w", encoding="utf-8").write('bots:\n  konan:\n    user_id: "%s"\n' % BOT_ID)
    if with_config:
        cfg = {"top_channels": [TOP], "roster_path": roster}
        if with_roots:
            cfg["workspace_roots"] = [workspace]
        with open(os.path.join(sdir, "dispatch-gate.json"), "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
    return sdir, workspace


def run_gate(sdir, payload, extra_env=None):
    env = {**os.environ, "MEETING_WATCHDOG_STATE_DIR": sdir}
    if extra_env:
        env.update(extra_env)
    out = subprocess.run([sys.executable, GATE], input=json.dumps(payload),
                        capture_output=True, encoding="utf-8", errors="replace", env=env)
    if out.stdout is None:
        raise AssertionError("gate stdout=None — spawn/decode 실패는 조용히 못 지나간다")
    denied = "permissionDecision" in out.stdout and '"deny"' in out.stdout
    return denied, out


def rows(sdir, basename):
    p = os.path.join(sdir, basename)
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def payload(chat_id=TOP, text=None, tool="mcp__plugin_discord_discord__reply",
            origin=None, cwd="__default__", workspace=None):
    ti = {"chat_id": chat_id,
          "text": text if text is not None else "<@%s> 작업 착수" % BOT_ID}
    if origin is not None:
        ti["origin"] = origin
    data = {"tool_name": tool, "tool_input": ti}
    if cwd == "__default__":
        data["cwd"] = workspace
    elif cwd is not None:
        data["cwd"] = cwd
    return data


def main():
    print("⑤-0 origin_reclassified denial 로그 (체크리스트 선두)")
    sdir, ws = setup()
    denied, _ = run_gate(sdir, payload(origin="bridge_notice", workspace=ws))
    POS_CTRL[0] += 1
    dn = rows(sdir, "dispatch-gate-denials.jsonl")
    check("0 위조 origin=bridge_notice → deny(통과 티켓 아님)", denied)
    check("0 denial 로그 origin_reclassified=true",
          len(dn) == 1 and dn[0].get("origin_reclassified") is True
          and dn[0].get("origin_effective") == "model"
          and dn[0].get("origin_claimed") == "bridge_notice", str(dn))

    print("⑤-1 기본 차단·통과 축")
    sdir, ws = setup()
    denied, _ = run_gate(sdir, payload(workspace=ws))
    POS_CTRL[0] += 1
    check("1 top+봇멘션+마커(in-cwd) → deny(양성)", denied)
    dn = rows(sdir, "dispatch-gate-denials.jsonl")
    check("1 denial 로그 1행·origin_claimed 부재(reclassify false)",
          len(dn) == 1 and dn[0].get("origin_reclassified") is False)

    denied, out = run_gate(sdir, payload(chat_id="333333333333333333",
                                         workspace=ws))
    NEG_CTRL[0] += 1
    check("2 비-top(스레드) → pass(음성 미끼)", not denied and out.stdout == "")

    denied, _ = run_gate(sdir, payload(text="봇 없이 작업 이야기만",
                                       workspace=ws))
    NEG_CTRL[0] += 1
    check("3 멘션 없음 → pass", not denied)

    denied, _ = run_gate(sdir, payload(tool="Bash", workspace=ws))
    NEG_CTRL[0] += 1
    check("4 비대상 도구(bridge 직접발신 구조 음성, D5) → pass", not denied)

    print("⑤-2 cwd 가드 (D2 — 85-doc 차단 1 수리)")
    sdir, ws = setup()
    denied, _ = run_gate(sdir, payload(cwd="/tmp/unrelated-project",
                                       workspace=ws))
    NEG_CTRL[0] += 1
    check("5 out-of-cwd(무관 프로젝트) → pass — 85-doc §C.4 반례 폐합",
          not denied)
    denied, _ = run_gate(sdir, payload(cwd=None, workspace=ws),
                         extra_env={"PWD": ws})
    POS_CTRL[0] += 1
    check("6 cwd 부재 → $PWD fallback(in-root) = deny(양성)", denied)
    denied, _ = run_gate(sdir, payload(cwd=None, workspace=ws),
                         extra_env={"PWD": "/tmp/unrelated-project"})
    NEG_CTRL[0] += 1
    check("7 cwd 부재 + $PWD out-of-root → pass", not denied)
    prefix_sibling = ws + "-sibling"
    os.makedirs(prefix_sibling, exist_ok=True)
    denied, _ = run_gate(sdir, payload(cwd=prefix_sibling, workspace=ws))
    NEG_CTRL[0] += 1
    check("8 prefix sibling(root-other) → pass(경계 정확 결박)", not denied)

    print("⑤-3 carve-out 계약·관측 로그 (코난 관측 ①)")
    sdir, ws = setup()
    denied, _ = run_gate(sdir, payload(
        text="[공지] <@%s> 작업 재개 안내" % BOT_ID, workspace=ws))
    ob = rows(sdir, "dispatch-gate-observations.jsonl")
    POS_CTRL[0] += 1
    check("9 계약: 자칭 carve-out+봇멘션+마커 = pass (fail-closed 승격 ❌)",
          not denied)
    check("9 그 조합 = 관측 로그 정확 1행(태그·멘션 기록)",
          len(ob) == 1 and ob[0].get("tag") == "[공지]"
          and ob[0].get("bot_mentions") == [BOT_ID], str(ob))
    denied, _ = run_gate(sdir, payload(text="[공지] 오늘 일정 안내입니다",
                                       workspace=ws))
    ob = rows(sdir, "dispatch-gate-observations.jsonl")
    NEG_CTRL[0] += 1
    check("10 멘션 없는 carve-out → pass + 관측 로그 무증가(음성)",
          not denied and len(ob) == 1)

    print("⑤-4 fail-closed·비활성 축")
    sdir, ws = setup(with_roster=False)
    denied, _ = run_gate(sdir, payload(text="<@999888777> 작업 착수",
                                       workspace=ws))
    POS_CTRL[0] += 1
    dn = rows(sdir, "dispatch-gate-denials.jsonl")
    check("11 로스터 미독 → 멘션 동반 발주 deny(fail-closed)",
          denied and dn and dn[-1].get("roster_fail_closed") is True)

    sdir, ws = setup(with_config=False)
    denied, _ = run_gate(sdir, payload(workspace=ws))
    NEG_CTRL[0] += 1
    check("12 config 부재 → 비활성 pass(설치층이 잡음)", not denied)

    sdir, ws = setup(with_roots=False)
    denied, _ = run_gate(sdir, payload(workspace=ws))
    NEG_CTRL[0] += 1
    check("13 workspace_roots 부재 → 비활성 pass(반쪽 config 도 비활성)",
          not denied)

    print("⑤-5 연결 probe (D2 — 0번 칸)")
    wired = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
    json.dump({"hooks": {"PreToolUse": [{"matcher": "mcp__plugin_discord",
               "hooks": [{"type": "command",
                          "command": "python3 %s" % GATE}]}]}}, wired)
    wired.close()
    sdir, ws = setup()
    out = subprocess.run([sys.executable, GATE, "--probe"],
                        capture_output=True, encoding="utf-8", errors="replace",
                        env={**os.environ, "MEETING_WATCHDOG_STATE_DIR": sdir,
                             "DISPATCH_GATE_SETTINGS": wired.name})
    POS_CTRL[0] += 1
    check("14 probe 5/5 PASS(wiring·config·deny·비-top·out-cwd)",
          out.returncode == 0 and "PROBE PASS 5/5" in out.stdout, out.stdout)
    check("14 probe 관측 로그 누적 info 줄 표기(판독 보조)",
          "관측 로그 누적" in out.stdout, out.stdout)

    unwired = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
    json.dump({"hooks": {}}, unwired)
    unwired.close()
    out = subprocess.run([sys.executable, GATE, "--probe"],
                        capture_output=True, encoding="utf-8", errors="replace",
                        env={**os.environ, "MEETING_WATCHDOG_STATE_DIR": sdir,
                             "DISPATCH_GATE_SETTINGS": unwired.name})
    NEG_CTRL[0] += 1
    check("15 미배선 settings → probe FAIL(음성 미끼)",
          out.returncode == 1 and "wiring" in out.stdout, out.stdout)

    sdir2, _ws2 = setup(with_roots=False)
    out = subprocess.run([sys.executable, GATE, "--probe"],
                        capture_output=True, encoding="utf-8", errors="replace",
                        env={**os.environ, "MEETING_WATCHDOG_STATE_DIR": sdir2,
                             "DISPATCH_GATE_SETTINGS": wired.name})
    NEG_CTRL[0] += 1
    check("16 workspace_roots 부재 → probe FAIL(«비활성=완료» 차단)",
          out.returncode == 1, out.stdout)
    os.unlink(wired.name)
    os.unlink(unwired.name)

    total = len(PASS) + len(FAIL)
    POS_CTRL[1], NEG_CTRL[1] = 6, 11  # 음성: 2·3·4·5·7·8·10·12·13·15·16
    expected_min = 20
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
