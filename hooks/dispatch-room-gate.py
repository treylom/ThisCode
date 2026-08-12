#!/usr/bin/env python3
"""dispatch-room-gate.py — Gate A: top-level 채널 봇 발주 차단 (ThisCode port).

Spec: obsidian-ai-vault meetings/2026-08-12-dispatch-meeting-gate/
      70-karpathy-track2-porting-spec.md v2.9 §1 D1(ThisCode Discord)·D2·D5.
Vault 정본: obsidian-ai-vault/.claude/hooks/dispatch-room-gate.py (Gate A
v1.1, 3/3 GREEN) — 제품 델타 = 하드코딩 채널/로스터 → install config.

Wiring (install-hooks): PreToolUse matcher
  "mcp__plugin_discord_discord__reply|mcp__plugin_discord_discord__edit_message"
Config: <state>/dispatch-gate.json
  {"top_channels": ["<channel_id>", ...], "roster_path": "/abs/bot-roster.yaml"}
  state = $MEETING_WATCHDOG_STATE_DIR or ~/.claude-state.
  config 부재/빈 top_channels = 게이트 비활성(exit 0) — 설치 완료 판정은
  `--probe` 가 막는다(연결 증명 0번 칸: config 없이는 probe 가 FAIL).

Origin (D5 v2.3): PreToolUse 는 구조상 model call-path 다 — tool_input 의
`origin` 필드는 host wrapper 상수가 아니라 모델 payload 유래이므로 어떤
값이든 통과 티켓이 될 수 없다. `bridge_notice` 를 자칭하면 model 로
재분류(fail-closed)하고 denial 로그에 `origin_reclassified: true` 를 남긴다.
(브리지 장애 알림의 실제 경로 = templates/bridge.py 직접 발신 — PreToolUse
비경유 = 구조적 음성. fixture 로 명기.)

Probe (`--probe`): ①wiring — settings.json 에 본 훅 PreToolUse 등재
②양성 — synthetic 발주 payload 가 실제 decide() 경로에서 deny
③음성(미끼) — 비-top 채널 동일 payload 가 pass. 3/3 아니면 exit 1.
"""

import json
import os
import re
import sys
import time

MARKERS = ["발주", "검수", "작업", "구현", "수리", "착수", "진행", "분석",
           "작성", "dispatch", "회수", "테스트", "검증"]
CARVEOUT = re.compile(r"\[(공지|단발|핑)\]")
MENTION = re.compile(r"<@!?(\d+)>")
ROSTER_ID = re.compile(r'user_id:\s*"(\d+)"')


def state_dir():
    return os.environ.get("MEETING_WATCHDOG_STATE_DIR") or os.path.expanduser(
        "~/.claude-state")


def load_config():
    try:
        cfg = json.load(open(os.path.join(state_dir(), "dispatch-gate.json"),
                             encoding="utf-8"))
        return {"top_channels": set(map(str, cfg.get("top_channels", []))),
                "roster_path": cfg.get("roster_path", "")}
    except Exception:
        return None


def load_roster_ids(roster_path):
    """None = 미독(fail-closed 신호) / set = 실측 로스터."""
    try:
        parsed = set(ROSTER_ID.findall(
            open(roster_path, encoding="utf-8").read()))
        return parsed or None
    except Exception:
        return None


def decide(data, cfg):
    """(verdict, record) — verdict ∈ {'pass','deny'}; record = 로그/사유."""
    tool = data.get("tool_name", "")
    if not tool.endswith("__reply") and not tool.endswith("__edit_message"):
        return "pass", {"why": "non-target tool"}
    ti = data.get("tool_input", {}) or {}
    chat_id = str(ti.get("chat_id", ""))
    text = str(ti.get("text", "") or "")

    origin_claimed = ti.get("origin")
    origin_reclassified = bool(origin_claimed)  # 모델 payload 유래 = 전부 무효

    if chat_id not in cfg["top_channels"]:
        return "pass", {"why": "not a top-level channel"}
    if CARVEOUT.search(text):
        return "pass", {"why": "carve-out tag"}

    roster_ids = load_roster_ids(cfg["roster_path"])
    mentioned = set(MENTION.findall(text))
    if roster_ids is None:
        # 로스터 미독 = fail-closed: 멘션 전부를 잠재 봇으로 간주
        bot_mentions = mentioned
    else:
        bot_mentions = mentioned & roster_ids
    if not bot_mentions:
        return "pass", {"why": "no bot mention"}
    if not any(m in text for m in MARKERS):
        return "pass", {"why": "no dispatch marker"}
    return "deny", {
        "chat_id": chat_id,
        "bot_mentions": sorted(bot_mentions),
        "text_head": text[:120],
        "origin_claimed": origin_claimed,
        "origin_effective": "model",
        "origin_reclassified": origin_reclassified,
        "roster_fail_closed": roster_ids is None,
    }


def write_denial(record, probe=False):
    try:
        log_path = os.path.join(state_dir(), "dispatch-gate-denials.jsonl")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(
                {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                 **({"probe": True} if probe else {}), **record},
                ensure_ascii=False) + "\n")
    except Exception:
        pass


DENY_REASON = (
    "[회의실 게이트 · meeting-protocol §1] 본문 채널에서 봇에게 발주하려 "
    "합니다 — 봇 간 작업 위임은 전용 스레드(회의실 4-file 동반)에서만. "
    "통과 경로: ① 회의 스레드/DM 에서 발신(없으면 회의실+스레드 먼저 생성) "
    "② 단발 공지·생존 핑이면 [공지]/[단발]/[핑] 태그 명기 "
    "③ 사람 대상 메시지는 봇 멘션 제거. (spec: dispatch-meeting-gate 70-doc "
    "v2.9 D1 — ThisCode port)"
)


def hook_main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cfg = load_config()
    if not cfg or not cfg["top_channels"]:
        return 0                      # 미설정 = 비활성 (probe 가 설치층에서 잡음)
    verdict, record = decide(data, cfg)
    if verdict == "pass":
        return 0
    write_denial(record)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY_REASON,
        }
    }, ensure_ascii=False))
    return 0


def probe_main():
    """연결 증명 0번 칸 — 3칸 전부 PASS 여야 설치 완료를 말할 수 있다."""
    results = []

    settings_path = os.environ.get("DISPATCH_GATE_SETTINGS") or \
        os.path.expanduser("~/.claude/settings.json")
    wired = False
    try:
        body = open(settings_path, encoding="utf-8").read()
        parsed = json.loads(body)
        for entry in (parsed.get("hooks", {}).get("PreToolUse", []) or []):
            for h in entry.get("hooks", []) or []:
                if "dispatch-room-gate.py" in str(h.get("command", "")):
                    wired = True
    except Exception:
        pass
    results.append(("wiring(settings.json PreToolUse)", wired))

    cfg = load_config()
    if not cfg or not cfg["top_channels"]:
        results.append(("config(top_channels)", False))
        results.append(("deny(양성)", False))
        results.append(("pass(음성 미끼)", False))
    else:
        results.append(("config(top_channels)", True))
        top = sorted(cfg["top_channels"])[0]
        roster_ids = load_roster_ids(cfg["roster_path"])
        probe_id = sorted(roster_ids)[0] if roster_ids else "999999999999"
        payload = {"tool_name": "mcp__plugin_discord_discord__reply",
                   "tool_input": {"chat_id": top,
                                  "text": "<@%s> 작업 착수 (probe)" % probe_id}}
        verdict, record = decide(payload, cfg)
        if verdict == "deny":
            write_denial(record, probe=True)
        results.append(("deny(양성)", verdict == "deny"))
        neg = {"tool_name": "mcp__plugin_discord_discord__reply",
               "tool_input": {"chat_id": "000000000000000000",
                              "text": "<@%s> 작업 착수 (probe)" % probe_id}}
        verdict2, _ = decide(neg, cfg)
        results.append(("pass(음성 미끼)", verdict2 == "pass"))

    ok = sum(1 for _n, r in results if r)
    for name, r in results:
        print("  [%s] %s" % ("PASS" if r else "FAIL", name))
    print("PROBE %s %d/%d" % ("PASS" if ok == len(results) else "FAIL",
                              ok, len(results)))
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    if "--probe" in sys.argv:
        sys.exit(probe_main())
    sys.exit(hook_main())
