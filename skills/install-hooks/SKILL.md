---
name: install-hooks
description: thiscode 훅 7개의 등록 상태를 검사하고, 옛 병합 잔존을 정리한다 (hooks/hooks.json 없는 체크아웃에서는 예전처럼 ~/.claude/settings.json 에 안전 merge)
disable-model-invocation: true
allowed-tools: Bash Read Write Edit AskUserQuestion
---

사용자가 이 스킬을 호출했다 — 아래 단계를 순서대로 지금 수행한다.

# /thiscode:install-hooks — hook 등록 스킬

이 호출의 구현은 본 `skills/install-hooks/SKILL.md`다. 별도의 `commands/install-hooks.md`는 제공하지 않는다.

> 순정 Claude Code 에서 soul.md / WD memory / 슬래시 detect / 회귀 self-check 가 자동으로 도는 데 필요한 훅 7개를 다룬다.
> **플러그인을 깔면 훅은 이미 등록돼 있다** — 플러그인에 `hooks/hooks.json` 이 동봉되고 Claude Code 가 그걸 직접 싣는다.
> 훅은 **봇 세션에서만**(`DISCORD_STATE_DIR` 이 있을 때만) 동작한다 — 일반 개발 세션에서는 래퍼가 아무 출력 없이 통과시킨다.
> 그래서 이 스킬이 하는 일은 «검사 + 옛 병합 잔존 정리» 다. `hooks/hooks.json` 이 없는 체크아웃이면 예전처럼 `~/.claude/settings.json` 에 안전 merge 한다(기존 사용자 hook 보존).

$ARGUMENTS

---

## 모드 두 개 — 어느 쪽인지는 파일 하나가 정한다

| 모드 | 조건 | 스크립트가 하는 일 |
|---|---|---|
| **플러그인 모드** (기본) | 플러그인 루트에 `hooks/hooks.json` 이 있다 | 병합하지 않는다. 옛 병합 방식으로 `~/.claude/settings.json` 에 남은 **같은** 훅만 지운다(안 지우면 한 번 일어난 일에 훅이 두 번 발화한다) + `--verify` 로 검사한다 |
| **병합 모드** (fallback) | `hooks/hooks.json` 이 없다 | 예전 그대로 `~/.claude/settings.json` 에 훅 7개를 안전 merge 한다 |

되돌리기는 `hooks/hooks.json` 하나를 지우는 것으로 끝난다 — 그러면 자동으로 병합 모드로 돌아간다.

**봇 세션 가드**: `hooks/hooks.json` 의 명령은 전부 `hooks/lib/bot-only.sh` 를 거친다.
이 래퍼는 `DISCORD_STATE_DIR` 이 비어 있으면 stdin 만 비우고 **출력 0 바이트로 exit 0** 한다 —
훅이 모든 세션에 실리되 «봇 세션에서만» 동작하게 하는 것이 이 한 장이다.
있으면 대상 훅을 그대로 실행한다(`.py` 는 python3, 그 외는 bash · stdin·인자·종료코드 전달).

## 등록할 hooks 7개

1. **SessionStart** → `bot-session-init.sh`
   - soul.md (페르소나) 자동 inject
   - WD memory 인덱스 자동 inject
   - 공통 규율 (페르소나·슬래시·메모리 분기) inject

2. **UserPromptSubmit** → `discord-slash-cmd.sh`
   - 프롬프트 첫 줄 `/cmd` 매칭 → Skill 도구 invoke 강제

3. **UserPromptSubmit** → `regression-self-check.sh`
   - 4-gate self-check (Discord reply / 단정 표현 / single-grep / skill invoke) 매 응답 전 환기

4. **UserPromptSubmit** → `rule-router.sh`
   - 프롬프트 task-type 키워드 매칭 → 해당 rule 핵심 게이트 자동 주입 (Layer-1 enforcement, docs/rules-system.md). 정적 self-check 보완 — 상황 매칭이라 무뎌지지 않음. fail-open(무매칭/jq부재 → 무출력)

5. **PreToolUse** → `dispatch-room-gate.py`
   - 최상위 채널에서 다른 봇에게 일을 시키는 답장을 막는다(발주는 전용 스레드에서) — 설정 파일이 없으면 비활성(그대로 통과)

6. **Stop** → `meeting-stop-reread.sh`
   - active meeting 이 열려 있는 봇 세션이면 종료 전 회의 state 재독을 요청
   - active meeting 없음 / 일반 개발 세션 / 재귀 Stop = fail-open allow-stop

7. **Stop** → `reply-gate.sh`
   - Discord 로 온 요청인데 답장 도구를 한 번도 안 쓰고 턴을 끝내려 하면 막는다 —
     터미널에만 찍힌 출력은 사용자에게 **도달하지 않는다**
   - Discord 턴이 아니면 fail-open(그대로 통과)

---

## 진행 흐름

### Step 1. thiscode plugin 위치 detect

```bash
# thiscode plugin 위치 자동 detect — 실제 설치 위치 전부 순서대로 probe.
# (정식 marketplace / 수동 clone / 정식 install cache / dev clone / 버전 cache)
# bare `[ -d hooks ]` 아닌 hooks/bot-session-init.sh 실재로 판정 (stale dir 회피).
#
# Fix F (2026-08-10, 루돌프 4차 실측): 첫 매치 승리 방식이라 후보 #1(마켓 클론)이 구판이면
# 후보 #5(버전 캐시, freshest)를 두고도 구판이 이겨 rules-seed.md 를 무징후로 누락시켰다.
# CLAUDE_PLUGIN_ROOT 를 1순위로 — 마크다운 원문 리터럴, Claude Code 가 이 문서를 로드하며
# 실제 설치 경로로 치환한다(셸 풀이 ❌ — code.claude.com/docs/en/plugins-reference.md
# "Environment variables": skill/command content 는 placeholder 등장 위치 전부 치환).
# 미치환(빈 값)이면 아래 5-후보 폴백으로 무회귀 낙하.
PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"
if [ -z "$PLUGIN_DIR" ] || [ ! -f "$PLUGIN_DIR/hooks/bot-session-init.sh" ]; then
  PLUGIN_DIR=""
  for _cand in \
    "$HOME/.claude/plugins/marketplaces/thiscode-marketplace" \
    "$HOME/.claude/plugins/thiscode" \
    "$HOME/.claude/plugins/cache/local/thiscode" \
    "$HOME/code/thiscode" \
    "$HOME"/.claude/plugins/cache/thiscode-marketplace/thiscode/*; do
    if [ -f "$_cand/hooks/bot-session-init.sh" ]; then PLUGIN_DIR="$_cand"; break; fi
  done
fi

if [ -z "$PLUGIN_DIR" ]; then
  echo "❌ thiscode 의 hooks/ 못 찾음 — plugin install (또는 git clone) 먼저"
  exit 1
fi
```

### Step 2. 스크립트 1회 호출 — 모드는 스크립트가 판단한다

이 로직은 `scripts/install-hooks.sh` 한 곳에 산다. 이 문서와 `create-bot` 이 **같은 스크립트**를
부른다 — 예전처럼 양쪽에 같은 병합식을 베껴 두면 한쪽만 고쳐져 조용히 갈라진다.

```bash
bash "$PLUGIN_DIR/scripts/install-hooks.sh"
```

- **플러그인 모드**면 병합하지 않는다. 옛 병합 잔존이 있을 때만 그것을 지우고(백업 후) 무엇을 지웠는지 알려준다.
  지울 것이 없으면 `settings.json` 을 아예 손대지 않는다.
- **병합 모드**면 예전대로 병합한다. 백업은 스크립트가 알아서 만든다 (`settings.json.bak-<시각>`).
  **기존 훅은 그대로 둔다** — 같은 명령을 두 번 넣지 않으므로 다시 실행해도 안전하다.
- 어느 모드든 판정·수정 엔진은 `jq` 가 있으면 jq, 없으면 `node` 로 **같은 규칙**을 쓴다.
  둘 다 없을 때만 멈추고(`exit 2`) 무엇을 설치하면 되는지 알려준다.
- 바꾸기 전에 확인하려면 `--dry-run`(플러그인 모드에서는 «지울 목록»만 보여준다),
  다른 홈으로 시험하려면 `--home <디렉터리>` 를 붙인다.

### Step 4. 검증

```bash
bash "$PLUGIN_DIR/scripts/install-hooks.sh" --verify
```

`exit 0` = 네 이벤트 — `"SessionStart"` · `"UserPromptSubmit"` · `"PreToolUse"` ·
`"Stop"`(회의 재독 `meeting-stop-reread.sh` 와 답장 게이트 `reply-gate.sh` 가 여기 붙는다) — 에
필요한 훅이 전부 등록돼 있고, 등록된 명령의 **파일이 실재한다**. 무엇을 읽는지는 모드가 정한다:
플러그인 모드면 `hooks/hooks.json`(+ 래퍼 실재 + `settings.json` 에 옛 병합 잔존 0),
병합 모드면 `~/.claude/settings.json`.
`exit 1` 이면 빠진 항목을 줄마다 이름으로 알려준다 — 파일 실재 검사가 중요한데, 등록만 되고
파일이 없으면 아무 오류 없이 조용히 아무 일도 안 일어나기 때문이다.

플러그인 모드에는 줄 하나가 더 붙는다: `settings.json` 의 `enabledPlugins` 에 thiscode 가
켜져 있으면 「등록 확인」, 없으면 「미확인 …」 **경고만** 낸다(실패로 세지 않는다).
개발 체크아웃(`--plugin-dir`)은 마켓 설치가 아니라서 여기 안 잡히기 때문이다 —
그걸 실패로 잡으면 멀쩡한 설치가 거짓 실패한다.
이 층이 답할 수 있는 것은 「등록 파일이 완비됐나」까지다. Claude Code 가 실제로 실었는지는
새 봇 세션을 한 번 띄워 SessionStart 주입이 나오는지 보는 것으로 확인한다.

### Step 5. 새 세션에서 효과 확인

```bash
# 기존 claude 세션 종료
exit

# 새 세션 시작
claude
```

→ SessionStart hook 이 첫 응답 직전 stdout 으로 soul.md / 메모리 / 공통 규율 inject. 사용자가 첫 메시지 보내면 4-gate self-check 표 stdout 주입.

확인: 첫 응답에서 봇이 페르소나 어휘 + 시그니처 사용 → ✅

### Step 6. (다봇 워크스페이스) 회의실 게이트 구성 + 연결 probe

`dispatch-room-gate.py` 는 **top-level 공용 채널에서 봇이 다른 봇에게 작업을 지시하는 답장을 deny** 하는
PreToolUse 훅이다 (rules-seed Rule 3 과 같은 판정 기준). 봇이 2개 이상인
워크스페이스에서만 의미가 있다 — 단일 봇 설치면 이 Step 을 건너뛰어도 된다
(설정 파일이 없으면 게이트는 조용히 비활성).

```bash
STATE="${MEETING_WATCHDOG_STATE_DIR:-$HOME/.claude-state}"
mkdir -p "$STATE"
cat > "$STATE/dispatch-gate.json" <<EOF
{
  "top_channels": ["<공용 채널 id 1>", "<공용 채널 id 2>"],
  "roster_path": "<bot-roster.yaml 절대경로 — user_id: \"<id>\" 항목 보유>",
  "workspace_roots": ["<봇 WD/워크스페이스 절대경로 — 이 안(cwd)에서만 게이트 발화>"]
}
EOF

# 연결 probe (D2 cwd 가드 축 — 설치 완료 판정의 0번 칸): wiring(settings 등재)·config·
# in-cwd 양성 deny·비-top 음성 pass·out-cwd 음성 pass 5칸 전부 PASS 여야 완료
python3 "$PLUGIN_DIR/hooks/dispatch-room-gate.py" --probe
```

`PROBE PASS 5/5` 가 아니면 게이트 설치를 완료로 보고하지 않는다 — probe 가
막는 것이 바로 «등록만 하고 발화 확인 없는 설치»다. denial 기록 =
`$STATE/dispatch-gate-denials.jsonl` (probe 발 기록은 `"probe": true` 표기).

---

## 트러블슈팅

| 증상 | 원인 | 대응 |
|---|---|---|
| `jq: command not found` | jq 미설치 | `brew install jq` (Mac) / `apt install jq` (Linux) / **Windows: winget install jqlang.jq — 또는 jq 없이 node 폴백**: agent 가 아래 node 한 줄로 동일 merge 수행 (Windows 의 `jq`/`python` 은 스토어 스텁일 수 있어 node/bun 이 안전) |
| Windows에서 chmod 실패 | NTFS 는 POSIX chmod 미적용 (정상) | 무시하고 진행 — 검증 항목 아님 |
| SessionStart hook 작동 안 함 | settings.json 의 `hooks.SessionStart[].matcher` 가 다른 값 | matcher: "" (전체 match) 확인 |
| soul.md 안 inject | DISCORD_STATE_DIR 미설정 | claude 시동 시 `export DISCORD_STATE_DIR="$HOME/.claude/channels/discord-<bot-name>"` 명시 |
| 사용자 기존 hook 충돌 | jq merge unique_by 가 같은 command 매칭 못 함 | manual 검토 |

---

## (옵션) Stop 디버그 surface 훅

`hooks/stop-debug-surface.sh` 는 **opt-in** Stop 훅 — 세션 종료 시 cwd git repo 에
미커밋 source/test 파일이 있으면 stderr 로 한 줄 알림(디버그 작업 미저장 방지).

⚠️ **fail-OPEN 설계**: 이 훅은 **항상 exit 0**, **절대 세션 종료를 막지 않음**
(기존 `stop-pending-task-check.sh` 의 fail-CLOSED/exit 2 와 의도적으로 대비 —
디버그 체크가 봇을 종료 불가 상태로 가두지 않게). 정보 표출 전용.

기본 미등록. 원하면 `~/.claude/settings.json` 의 `hooks.Stop[]` 에 추가:

```json
{ "matcher": "", "hooks": [
  { "type": "command", "command": "bash '$PLUGIN_DIR/hooks/stop-debug-surface.sh'" }
] }
```

`stop-pending-task-check.sh` 와 공존 가능(대체 아님 — 둘 다 Stop 배열에 append).

---

## 관련 자원

- hooks 본문: [bot-session-init.sh](../../hooks/bot-session-init.sh) / [discord-slash-cmd.sh](../../hooks/discord-slash-cmd.sh) / [regression-self-check.sh](../../hooks/regression-self-check.sh) / [stop-debug-surface.sh](../../hooks/stop-debug-surface.sh) (opt-in)
- active meeting Stop reread(선택): [meeting-stop-reread.sh](../../hooks/meeting-stop-reread.sh) — bot session + active meeting + non-recursive Stop 일 때만 `{"decision":"block","reason":<재독 지시>}` (Stop 엔 hookSpecificOutput 변형 없음), 그 외 fail-open(빈 stdout + exit 0).
- DISCORD_STATE_DIR 구조: [discord-state-dir-README.md](../../templates/discord-state-dir-README.md)
- 첫 봇 생성: [create-bot](../create-bot/SKILL.md)
- 메인 wizard: [start](../../commands/start.md)
