---
name: slack-bridge
description: Use when creating a Slack bot that bridges to a local AI engine, Claude Code first (claude -p) with Codex CLI (codex exec) as an addable second engine. Covers Slack CLI authentication (near-full automation), app creation, engine-prefix routing (default claude, `codex:` prefix to switch), per-bot persona loading via CLAUDE.md (claude) / AGENTS.md (codex, when added), thread-scoped conversation continuity (claude --resume / codex exec resume), and round-trip verification. Also covers the Discord semi-auto path.
---

# Slack Agent Bridge — Slack 봇 ↔ 로컬 엔진(claude 우선 · codex 추가) 연결

> 코덱스 중심 판(정본 계보) = ThisCodex `skills/slack-bridge/SKILL.md`(commit 2aa250e). 본 문서는 같은 실측을 **Claude Code 사용자 1차 독자**로 재서술한 판이다 — 기본 구축 경로(1~7단계)는 claude 엔진 중심으로 서술하고, codex 는 **추가로 붙이는 두 번째 엔진**으로 다룬다(codex 관련 절·정직 표기는 전부 보존, 한 글자도 약화하지 않는다).

Slack 워크스페이스에 봇을 만들고, 메시지를 로컬 AI 엔진(Claude Code `claude -p` 기본 / Codex CLI `codex exec` 추가)으로 라우팅해 스레드로 답하게 하는 전 공정. 2026-08-05 macOS 에서 전 단계 실측 검증됨(왕복·페르소나 로딩 포함). Windows 는 설치 명령만 다르고 공정은 동일하다 — Windows 실측은 아직 없으므로 어긋나는 단계가 나오면 그 단계를 기록하고 멈춘다.

## 전제

- Slack CLI v4.6+ — macOS: `curl -fsSL https://downloads.slack-edge.com/slack-cli/install.sh | bash` / Windows: https://tools.slack.dev/slack-cli 의 Windows 설치 안내(공식) 사용
- Slack 워크스페이스 = **본인이 앱을 설치할 권한이 있는 곳**이어야 한다 — 수강생 실습은 본인 무료 워크스페이스 신설로 충분(생성자 = 관리자). ⚠️ 회사 워크스페이스는 관리자 승인 정책에 걸릴 수 있다.
- 로컬에 `claude`(Claude Code, 기본 엔진) — 또는 추가로 `codex`(Codex CLI, 두 번째 엔진) — 중 최소 1개 설치·로그인 상태. **claude 하나만으로도 전 과정 재현 가능**: codex 미설치 상태에서 `codex:` 접두사 메시지는 스레드에 오류 답변으로 돌아올 뿐, claude 만으로 왕복 검증(5단계)·스레드 연속 대화(6단계) 모두 재현된다.
- Slack 워크스페이스에 로그인된 브라우저 (자동화 시: 브라우저 조작 도구)

> **포털(api.slack.com)에서 앱을 만들지 마세요** — 이 공정은 Slack CLI 가 앱 생성·설치·토큰 발급을 전부 처리합니다(`slack create`→`slack run`). 웹에 흔한 '봇 토큰 복사' 방식 튜토리얼과 다른 공식 경로라, 토큰을 직접 다룰 일이 없습니다.

## 1단계 — Slack CLI 인증 (사람 관문 1곳, 브라우저 자동화로 0곳 가능)

```bash
slack login --no-prompt
# 출력: /slackauthticket <티켓문자열>
```

1. 위 `/slackauthticket …` 한 줄을 **Slack 아무 채널·DM 에 붙여넣고 전송** → 권한 모달에서 **Confirm** → 챌린지 코드 표시됨.
   - 자동화: 브라우저 도구로 Slack 웹 열기 → 메시지 입력창에 명령 입력·전송 → Confirm 클릭 → 코드 읽기.
   - Claude Code 환경 = claude-in-chrome 으로 완전 자동 실측 성공(2026-08-05). **Codex 앱 환경(codex 를 추가로 붙일 때) = browser-use 도구로 같은 3동작(입력→Confirm→코드 회수)을 수행** — Codex 로 이 스킬을 쓸 때는 수동 안내 대신 browser-use 자동화를 기본 경로로 시도하고, 도구가 없으면 사람 관문 1곳으로 안내한다.
2. 코드로 인증 완료:

```bash
slack login --no-prompt --ticket <티켓> --challenge <코드>
slack auth list   # 워크스페이스·User ID 나오면 성공 (~/.slack/credentials.json)
```

## 2단계 — 앱 생성

```bash
slack create my-agent-bridge   # 템플릿 선택: Bolt Python starter
cd my-agent-bridge && pip install -r requirements.txt
```

## 3단계 — 엔진 브리지 리스너

`listeners/messages/agent_bridge.py` 생성(핵심부 — 전체 규칙: **기본은 claude**, 메시지가 `codex:` 로 시작하면 codex 로 전환. 답은 항상 스레드로):

```python
import os, subprocess
from slack_bolt import BoltContext, Say

ENGINE_TIMEOUT_SEC = int(os.environ.get("AGENT_BRIDGE_TIMEOUT", "180"))
CLAUDE_CMD = [os.path.expanduser("~/.local/bin/claude"), "-p", "--strict-mcp-config"]
CODEX_CMD = [os.path.expanduser("~/.nvm/versions/node/v24.14.1/bin/codex"), "exec", "--skip-git-repo-check"]
# ⚠️ 경로는 절대경로로 — `which` 는 세션 셸의 가짜 경로(shim)를 줄 수 있어 slack run 프로세스와 어긋난다 (실측 함정)

BOT_HOME = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot-home"))
CODEX_HOME = os.path.join(BOT_HOME, ".codex")

def _run_engine(cmd, prompt, engine="claude"):
    env = dict(os.environ)
    if engine == "codex":
        env["CODEX_HOME"] = CODEX_HOME  # 4단계 참조
    p = subprocess.run([*cmd, prompt], capture_output=True, text=True,
                       timeout=ENGINE_TIMEOUT_SEC, cwd=BOT_HOME, env=env)
    return (p.stdout or "").strip() or (p.stderr or "").strip() or f"(빈 출력 — exit {p.returncode})"

def agent_bridge_callback(context: BoltContext, say: Say, logger, message: dict):
    text = (message.get("text") or "").strip()
    if not text:
        return
    try:
        if text.lower().startswith("codex:"):
            engine, reply = "codex", _run_engine(CODEX_CMD, text[6:].strip(), "codex")
        else:
            engine, reply = "claude", _run_engine(CLAUDE_CMD, text, "claude")
        say(text=f"[{engine}] {reply[:3800]}", thread_ts=message.get("thread_ts") or message.get("ts"))
    except subprocess.TimeoutExpired:
        say(text=f"⏱️ 엔진 {ENGINE_TIMEOUT_SEC}초 초과", thread_ts=message.get("thread_ts") or message.get("ts"))
```

`listeners/messages/__init__.py` 에 등록:

```python
app.message(re.compile(".*", re.DOTALL))(agent_bridge_callback)
```

> 위는 메시지마다 엔진을 새로 단발 호출하는 버전이다. 스레드 안에서 이어 물었을 때 이전 대화를 기억하게 하려면 **6단계 — 스레드 연속 대화** 참고.

## 4단계 — 봇 페르소나·규칙 (soul 입히기)

`bot-home/` 폴더를 만들고 **CLAUDE.md**(claude 엔진용 — 기본 경로)와, codex 를 추가로 붙일 때는 **AGENTS.md**(codex 엔진용)에도 같은 규칙을 쓴다 — 각 엔진이 자기 정식 설정 파일로 규칙을 문다:

```markdown
너는 **토푸(Tofu)** — 이 워크스페이스의 Slack 비서 봇이다.
1. 항상 한국어로, 세 문장 이내로 답한다.
2. 모든 답 끝에 서명 `— 토푸 🫘` 를 붙인다.
3. 모르면 모른다고 말한다. 위험한 요청(삭제·결제)은 거절한다.
```

**⚠️ codex 봇을 추가로 붙일 때 — 전역 설정 충돌 (같은 머신에 다른 codex 봇이 살 때)**: codex 는 `~/.codex/AGENTS.md`(전역)도 읽는다. 전역에 다른 페르소나가 있으면 로컬 파일과 경합해 **다른 봇 이름으로 답할 수 있다** (실측: 2회 재현). 해법 = 전용 `CODEX_HOME` 으로 **상태·세션·페르소나·hook 격리**:

```bash
mkdir -p bot-home/.codex
ln -s ~/.codex/auth.json bot-home/.codex/auth.json   # 인증만 승계
cp bot-home/AGENTS.md bot-home/.codex/AGENTS.md       # 규칙은 봇 것만
```

⚠️ **`auth.json` 은 심링크라 계정·자격증명은 이 격리 밖이다** — `bot-home/.codex/auth.json` 이 `~/.codex/auth.json` 을 그대로 가리키므로 상태·세션·페르소나·hook 은 봇 전용이어도 로그인 계정은 전역과 공유된다. 계정까지 분리하려면 심링크 대신 별도로 로그인한 `auth.json` 을 `bot-home/.codex/` 에 직접 두면 된다.

깨끗한 머신(수강생 환경)에서는 전역 AGENTS.md 가 비어 있어 이 단계가 없어도 로컬이 그대로 이긴다.

## 5단계 — 기동·초대·왕복 검증

```bash
slack run   # 앱 선택 → 팀 선택 → "Bolt app is running!" (Socket Mode·매니페스트 자동 설치)
```

1. Slack 에서 채널에 봇 초대: `/invite @<봇이름>` (⚠️ Bolt 기본 manifest 는 DM 탭 비활성 + `message.channels` 구독 = **채널 멤버여야 반응**)
2. **왕복 검증(합격선)**: 채널에 질문 → `[claude] …` 스레드 답 확인 → (codex 를 추가했다면) `codex: 질문` → `[codex] …` 확인
3. **페르소나 검증은 파일 존재가 아니라 행동으로**: "너는 누구야?" → 봇 이름 + 규칙의 서명(`— 토푸 🫘`)이 답에 실리는지 확인. 서명 = 규칙 로딩의 지문이다.
4. **프로세스 수명(정직 표기)**: `slack run` 을 띄운 실행 터미널을 닫으면 봇이 멈춘다 — 에러가 아니라 프로세스가 그 터미널에 붙어 있기 때문이다. 복구는 같은 폴더에서 `slack run` 재실행뿐이고, 스레드 기억은 `bot-home/.sessions.json` 에 남아 있어 기존 스레드에서 그대로 이어진다.

## 6단계 — 스레드 연속 대화 (구현·실측 완료)

Slack 스레드 `thread_ts`(또는 최상위 메시지면 `ts`) 를 엔진 세션 id 에 매핑해 **스레드 단위로 대화가 이어지게** 한다. 매핑은 `bot-home/.sessions.json` 에 스레드별 `{"claude": "<uuid>", "codex": "<session_id>"}` 로 원자 갱신 저장(`.tmp` 파일 후 `os.replace`).

- **claude**: 스레드 첫 메시지 = `--session-id <신규 uuid>` 로 세션 id 를 직접 지정해 생성. 이후 같은 스레드는 저장해둔 id 로 `--resume <id>` 재개.
- **codex**(추가 엔진): 저장된 세션이 있으면 `codex exec resume <SESSION_ID>` 로 재개. 없으면 평소대로 `codex exec` 실행 후, codex 가 세션 id 를 표준출력으로 안 주므로 **`CODEX_HOME/sessions/**/*.jsonl` 중 가장 최근 mtime 파일명에서 역산**해 저장한다 — 동시 요청이 겹치면 다른 스레드의 파일을 최신으로 잘못 집을 수 있어 신규 세션 생성 구간을 락으로 직렬화한다(아래 `_CODEX_LOCK`).

```python
SESSIONS_FILE = os.path.join(BOT_HOME, ".sessions.json")
_MAP_LOCK = threading.Lock()    # 맵 파일 원자 갱신
_CODEX_LOCK = threading.Lock()  # codex 신규 세션 = 실행 후 최신 rollout 파일로 id 귀속 → 직렬화 필요

def _newest_codex_session() -> str | None:
    files = glob(os.path.join(CODEX_HOME, "sessions", "**", "*.jsonl"), recursive=True)
    if not files:
        return None
    m = re.search(r"([0-9a-f-]{36})\.jsonl$", max(files, key=os.path.getmtime))
    return m.group(1) if m else None

# claude 분기
sid = _session_map().get(thread_key, {}).get("claude")
if sid:
    reply = _run_engine([*CLAUDE_CMD, "--resume", sid], text, engine="claude")
else:
    sid = str(uuid.uuid4())
    reply = _run_engine([*CLAUDE_CMD, "--session-id", sid], text, engine="claude")
    _remember(thread_key, "claude", sid)

# codex 분기 (추가 엔진)
sid = _session_map().get(thread_key, {}).get("codex")
if sid:
    reply = _run_engine([*CODEX_CMD, "resume", sid], prompt, engine="codex")
else:
    with _CODEX_LOCK:                      # 동시 실행 시 mtime 오귀속 방지
        reply = _run_engine(CODEX_CMD, prompt, engine="codex")
        new_sid = _newest_codex_session()
    if new_sid:
        _remember(thread_key, "codex", new_sid)
```

**라이브 검증(2026-08-05)**: 한 스레드에서 "내 별명은 두부야" 전송 후 되묻기("내 별명이 뭐라고 했지?") → `[claude] 두부님이에요! — 토푸 🫘`. 같은 스레드에 `codex: 내 별명이 뭐라고 했지?` → `[codex] 두부라고 했어! — 토푸 🫘`. 두 엔진 모두 세션 기억 복원 + 페르소나 서명 유지를 확인했다.

**세션 맵 크기(정직 표기)**: 오래 쓰면 `.sessions.json` 이 자란다(실습 규모 기준 수 KB 수준) — 지워도 안전하다. 지우면 스레드 기억만 리셋되고, 다음 메시지부터 그 스레드는 새 대화로 시작한다.

**codex resume 동시성(정직 표기)**: `_CODEX_LOCK` 은 **신규 세션 생성 구간만** 직렬화한다 — 이미 세션이 있는 스레드의 `codex exec resume` 자체는 잠금이 없다. 같은 Slack 스레드에 메시지가 거의 동시에 여러 개 오면 같은 codex 세션이 겹쳐 실행될 수 있다. 강의에서 다루는 단일 왕복(사람이 한 번에 한 메시지)에서는 문제가 되지 않지만, 운영으로 확장하려면 스레드별 직렬 큐가 필요하다.

진짜 라이브 TUI 상주 세션(우리 Discord 봇 방식)에 붙이려면 브리지 데몬 구조가 별도로 필요하다 — 이건 여전히 참이다.

## 7단계 — 회의 모드 (구현·라이브 실측 완료 2026-08-05)

> 정본 코드 = `tofu-agent-bridge/listeners/messages/agent_bridge.py`. 이 실습 리포지토리는 git 저장소가 아니다 — **본 SKILL.md 가 이 코드의 유일한 git 추적본**이라 발췌를 넉넉히 남긴다.

`회의:` 로 시작하는 메시지가 오면 그 스레드를 회의 모드로 전환한다. 이후 접두사 없는 모든 메시지에 **claude → codex 순서로 두 엔진이 순차 응답**한다(디스코드 회의처럼). `회의 종료` 로 시작하면 claude 가 대화록을 요약해 발신하고 모드를 해제한다.

⚠️ **회의 모드는 6단계의 세션 resume 을 쓰지 않는다.** 엔진별 세션 기억은 자기 발언만 담고 있어 상대 엔진의 발언을 못 보기 때문에, 매 턴 Slack API(`conversations_replies`)로 스레드 대화록 전체를 새로 읽어 프롬프트에 실어 두 엔진이 서로의 발언을 참고하게 한다(무상태). 즉 **일반 모드(1:1 왕복, 6단계)는 세션 resume**, **회의 모드(N:N 토론, 본 단계)는 대화록 재주입** — 상황이 다른 두 메커니즘이지 서로 모순이 아니다.

```python
MEETING_TRIGGER = "회의:"
MEETING_END = "회의 종료"
MEETING_HISTORY_LIMIT = 30  # 대화록 최근 N개 메시지만 프롬프트에 포함
MEETING_CHAR_LIMIT = 6000  # 대화록 총 문자수 상한 — 넘으면 앞부분부터 절단
MEETING_PARTICIPANT_PROMPT = (
    "너는 이 회의의 참석자 '{engine}'다. 아래는 지금까지의 회의 대화록이다. "
    "다른 참석자([claude]/[codex])의 발언을 참고해 세 문장 이내로 의견을 내라. 이미 나온 말 반복 금지.\n\n"
    "{transcript}"
)
MEETING_SUMMARY_PROMPT = "너는 이 회의의 서기다. 아래 회의 대화록을 세 문장 이내로 요약하라.\n\n{transcript}"


def _set_meeting(thread_key: str, active: bool) -> None:
    with _MAP_LOCK:
        m = _session_map()
        entry = m.setdefault(thread_key, {})
        if active:
            entry["meeting"] = True
        else:
            entry.pop("meeting", None)
        tmp = SESSIONS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(m, f)
        os.replace(tmp, SESSIONS_FILE)


def _meeting_transcript(client: WebClient, channel: str, thread_ts: str) -> str:
    # 회의 대화록 실시간 취득 — 사용자 발언은 "참석자: "로, 봇 발언은 이미 [claude]/[codex] 라벨이 있어 그대로.
    resp = client.conversations_replies(channel=channel, ts=thread_ts)
    lines = []
    for m in resp.get("messages", []):
        t = (m.get("text") or "").strip()
        if not t:
            continue
        lines.append(t if m.get("bot_id") else f"참석자: {t}")
    transcript = "\n".join(lines[-MEETING_HISTORY_LIMIT:])
    return transcript[-MEETING_CHAR_LIMIT:]


def _meeting_reply(client: WebClient, channel: str, thread_ts: str, engine: str, cmd: list[str]) -> str:
    # 매 턴 대화록을 새로 읽어 프롬프트에 실음(무상태) — 직전 발언(claude 등)까지 반영해야 하므로 캐시하지 않는다.
    transcript = _meeting_transcript(client, channel, thread_ts)
    prompt = MEETING_PARTICIPANT_PROMPT.format(engine=engine, transcript=transcript)
    return _run_engine(cmd, prompt, engine=engine)
```

콜백 안 분기 순서(회의 종료 → 회의 진행/트리거 → 기존 라우팅 순으로 검사, 6단계 코드 앞에 온다):

```python
# 회의 종료: claude 가 대화록 기반 요약 1회 발신 후 회의 모드 해제
if text.startswith(MEETING_END):
    summary = _run_engine(
        CLAUDE_CMD,
        MEETING_SUMMARY_PROMPT.format(transcript=_meeting_transcript(client, channel, thread_ts)),
        engine="claude",
    )
    say(text=f"[claude] 📋 회의 요약: {summary[:SLACK_MSG_LIMIT]}", thread_ts=thread_ts)
    _set_meeting(thread_key, False)
    return

# 회의 모드: `회의:` 트리거 또는 이미 진행 중인 스레드 → 접두사 불요, claude → codex 순차 응답.
in_meeting = _session_map().get(thread_key, {}).get("meeting", False)
if in_meeting or text.startswith(MEETING_TRIGGER):
    if not in_meeting:
        _set_meeting(thread_key, True)
    for engine, cmd in (("claude", CLAUDE_CMD), ("codex", CODEX_CMD)):
        reply = _meeting_reply(client, channel, thread_ts, engine, cmd)
        say(text=f"[{engine}] {reply[:SLACK_MSG_LIMIT]}", thread_ts=thread_ts)
    return

# (여기서부터 6단계의 codex:/claude 일반 라우팅 — 세션 resume 사용)
```

**라이브 검증(2026-08-05)**: 스레드에 `회의: <주제>` 로 개시 → 두 엔진이 각자 제안 발신하는 것을 확인 → 후속 메시지(접두사 없이)로 토론 유도 → 상호 참조 통합안 확인(claude = "타이머 딜 + 쿠폰 즉시 지급", codex = "7일 스탬프 패스" — 서로의 앞선 발언을 인용하며 좁혀짐) → `회의 종료` 전송 → `[claude] 📋 회의 요약: …` 발신 확인. **개시 → 토론 → 요약 전 구간 Slack 라이브 GREEN.**

## hook 절 — SessionStart 공지 주입

두 엔진 모두 세션 시작 시 훅으로 공지를 주입할 수 있다 — 스키마는 대칭이다.

- **claude**(기본 엔진): `bot-home/.claude/settings.json` 에 `SessionStart` 훅을 등록하고, `bot-home/.claude/hooks/notice.sh` 가 `additionalContext` JSON 을 표준출력으로 반환한다.
- **codex**(추가 엔진): `bot-home/.codex/hooks.json` 에 같은 이벤트를 같은 스키마로 등록한다.

```json
// bot-home/.claude/settings.json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "bash bot-home/.claude/hooks/notice.sh" } ] }
    ]
  }
}
```

```bash
# bot-home/.claude/hooks/notice.sh
#!/usr/bin/env bash
echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"공지: 오늘 회의는 15:00."}}'
```

```json
// bot-home/.codex/hooks.json — claude 와 동일 스키마
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "bash bot-home/.codex/hooks/notice.sh" } ] }
    ]
  }
}
```

⚠️ **codex 는 미신뢰 hook 을 에러 없이 조용히 스킵한다(무징후)** — hook 이 등록돼 있어도 신뢰 승인이 없으면 아무 표시 없이 실행되지 않는다. 문서화된 우회는 `codex exec --dangerously-bypass-hook-trust` 이지만, 이 우회는 **격리 CODEX_HOME 안 자기소유 hook 한정**이다 — 전역 codex 나 타인 hook 에는 쓰지 않는다.

⚠️ **hook 파일이 owner-writable 이면 변경 뒤 무검토 실행 여지가 남는다** — 완화: `chmod a-w bot-home/.codex/hooks.json bot-home/.claude/hooks/notice.sh`. 운영으로 확장할 때는 시작 시 SHA·owner·mode 검증도 필요하다.

## 8단계 — B-split: 엔진별 별도 Slack 봇 (2026-08-05 라이브 실측 GREEN)

7단계 회의 모드가 **한 봇 안에서** 접두사로 엔진을 나눴다면, 본 단계는 **엔진마다 별도 Slack 앱·봇**을 두는 확장이다 — 각 봇이 엔진 하나만 전담해 페르소나·서명이 완전히 갈린다.

1. 두 번째 앱 생성: `slack create` 로 매니페스트 이름만 바꿔 신설(예: `tofu-codex`).
2. `agent_bridge.py` 를 그대로 복제해 두 번째 앱에 배치.
3. 환경변수 `AGENT_BRIDGE_ENGINE=claude|codex` 로 앱마다 엔진을 고정한다 — 미설정 시 3단계/6단계의 `codex:` 접두사 라우팅이 그대로 살아 있어 **하위호환**이다(접두사 없으면 claude).
4. `bot-home` 은 앱마다 별도로 둔다 — CLAUDE.md/AGENTS.md 의 페르소나·서명이 봇마다 갈린다.
5. 봇간 무한루프 가드: 수신 메시지에 `bot_id` 가 실려 있으면(다른 봇의 발화) 응답하지 않는다.
6. 실행: 터미널 2개를 열어 각 앱 폴더에서 각각 전경으로 `slack run`.

**검증**: ① 정체성 왕복 — 각 봇에게 "너는 누구야?" → 각자 서명 확인. ② 회의 모드에서 봇 대 봇 상호 논평 — 한 스레드에서 각 봇이 자기 엔진으로 1회씩 응답해 서로의 발화를 참고하는지 확인.

## Discord 쪽 (반자동 — API 로 앱 생성 불가)

Discord 는 앱 생성·봇 토큰 발급 API 가 없다(2026-08-04 실측 확정). 자동화 가능한 것은 초대(OAuth2 URL)뿐:

1. https://discord.com/developers/applications → New Application → Bot 탭 → 토큰 발급 (수동, ~2분)
2. 이후 봇 구동·페르소나·상태 관리 = `/thiscode:create-bot` 온보딩이 담당 (skills/create-bot/SKILL.md) — Discord 봇 디렉토리·soul.md·hook 셋업까지 다룬다.

## 함정 목록 (전부 실측)

| 함정 | 증상 | 처방 |
|---|---|---|
| 엔진 경로를 `which` 로 잡음 | slack run 프로세스에서 엔진 못 찾음 | 절대경로 고정 |
| DM 으로 테스트 | 봇 무반응 (메시지 탭 비활성) | 채널 초대 후 채널에서 |
| codex 전역 AGENTS.md 경합 | 다른 봇 이름으로 답함 | CODEX_HOME 격리 |
| 티켓 유효시간 | 재부팅·지연 후 인증 실패 | 티켓은 쓰기 직전 발급 |
| cwd 를 홈으로 둠 | 페르소나·규칙 미주입("나는 그냥 Claude") | cwd = bot-home |
| codex 신규 세션 id 를 최신 rollout 파일 mtime 으로 역산 | 동시 실행 시 다른 스레드 세션 id 로 오귀속 위험 | 신규 세션 생성 구간을 락(`_CODEX_LOCK`)으로 직렬화 |
| 회의 모드 응답 대기 | 메시지 1개당 claude+codex 를 **순차** 호출 — 체감 1~2분 소요 | 기대치를 미리 안내(병렬 아님, 느린 게 정상) |

> 위 함정 표는 작성자 실측(2026-08-05 macOS) 기반이다 — 비작성자(수강생) 환경에서의 검증은 아직 실시되지 않았다.
