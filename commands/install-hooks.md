---
description: thiscode 의 SessionStart + UserPromptSubmit hooks 를 ~/.claude/settings.json 에 안전 merge (기존 hook 보존)
allowed-tools: Bash Read Write Edit AskUserQuestion
disable-model-invocation: true
---

# /thiscode:install-hooks — hook 등록

> 순정 Claude Code 에서 soul.md / WD memory / 슬래시 detect / 회귀 self-check 자동 작동을 위해 hooks 를 `~/.claude/settings.json` 에 등록. 기존 사용자 hook 보존 (jq merge).

$ARGUMENTS

---

## 등록할 hooks 4개

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

5. **Stop** → `meeting-stop-reread.sh`
   - active meeting 이 열려 있는 봇 세션이면 종료 전 회의 state 재독을 요청
   - active meeting 없음 / 일반 개발 세션 / 재귀 Stop = fail-open allow-stop

---

## 진행 흐름

### Step 1. thiscode plugin 위치 detect

```bash
# thiscode plugin 위치 자동 detect — 실제 설치 위치 전부 순서대로 probe.
# (정식 marketplace / 수동 clone / 정식 install cache / dev clone / 버전 cache)
# bare `[ -d hooks ]` 아닌 hooks/bot-session-init.sh 실재로 판정 (stale dir 회피).
PLUGIN_DIR=""
for _cand in \
  "$HOME/.claude/plugins/marketplaces/thiscode-marketplace" \
  "$HOME/.claude/plugins/thiscode" \
  "$HOME/.claude/plugins/cache/local/thiscode" \
  "$HOME/code/thiscode" \
  "$HOME"/.claude/plugins/cache/thiscode-marketplace/thiscode/*; do
  if [ -f "$_cand/hooks/bot-session-init.sh" ]; then PLUGIN_DIR="$_cand"; break; fi
done

if [ -z "$PLUGIN_DIR" ]; then
  echo "❌ thiscode 의 hooks/ 못 찾음 — plugin install (또는 git clone) 먼저"
  exit 1
fi
```

### Step 2. ~/.claude/settings.json 백업

```bash
SETTINGS="$HOME/.claude/settings.json"
[ -f "$SETTINGS" ] && cp "$SETTINGS" "$SETTINGS.backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$HOME/.claude"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
```

### Step 3. jq 로 안전 merge

```bash
PATCH=$(cat <<EOF
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash '$PLUGIN_DIR/hooks/bot-session-init.sh'",
            "timeout": 10
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash '$PLUGIN_DIR/hooks/discord-slash-cmd.sh'",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "bash '$PLUGIN_DIR/hooks/regression-self-check.sh'",
            "timeout": 3
          },
          {
            "type": "command",
            "command": "bash '$PLUGIN_DIR/hooks/rule-router.sh'",
            "timeout": 3
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash '$PLUGIN_DIR/hooks/meeting-stop-reread.sh'",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
EOF
)

# 기존 hook 보존 + thiscode hook append
# 순서 보존 병합: matcher별 그룹 유지(등장 순), 내부 hook은 type+command+timeout 키로 첫 등장만
jq -s 'def uniqHooks: reduce .[] as $x ([]; if (map(.type == $x.type and .command == $x.command and .timeout == $x.timeout) | any) then . else . + [$x] end);
def mergeEv($a; $b):
  reduce (($a + $b) | .[]) as $g ({order: [], map: {}};
    (($g.matcher // "")) as $m
    | if (.map | has($m)) then (.map[$m].hooks += ($g.hooks // []))
      else (.order += [$m] | .map[$m] = ($g + {matcher: $m, hooks: ($g.hooks // [])})) end)
  | [ .map[.order[]] | (.hooks |= uniqHooks) ];
. as [$s, $p] | ($s * $p)
| .hooks.SessionStart     = mergeEv($s.hooks.SessionStart // [];     $p.hooks.SessionStart // [])
| .hooks.UserPromptSubmit = mergeEv($s.hooks.UserPromptSubmit // []; $p.hooks.UserPromptSubmit // [])
| .hooks.Stop             = mergeEv($s.hooks.Stop // [];             $p.hooks.Stop // [])' \
  "$SETTINGS" <(echo "$PATCH") > "$SETTINGS.tmp"
mv "$SETTINGS.tmp" "$SETTINGS"
```

⚠️ jq merge 정확성 보장 — agent 가 사용자 기존 settings.json 의 hook 들을 보존하면서 thiscode hook 만 추가.

> **jq 부재 시 (Windows 등) node 폴백** — jq 를 설치하지 못하는 환경이면 agent 가 같은 merge 를 node 로 수행한다 (동일 보존 규칙: 기존 hook + thiscode hook, command 기준 dedupe):
>
> ```bash
> # $PATCH = Step 3 의 heredoc 문자열 그대로 (파일 불필요 — 문자열 인자로 전달)
> node -e '
> const fs = require("fs");
> const a = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
> const b = JSON.parse(process.argv[2]);
> const merged = { ...a, hooks: { ...(a.hooks || {}) } };
> for (const ev of ["SessionStart", "UserPromptSubmit", "Stop"]) {
>   const groups = new Map();  // matcher별 바깥 그룹 병합
>   for (const g of [...(a.hooks?.[ev] || []), ...(b.hooks?.[ev] || [])]) {
>     const m = g.matcher || "";
>     if (!groups.has(m)) groups.set(m, { ...g, matcher: m, hooks: [] });
>     const tgt = groups.get(m);
>     for (const h of g.hooks || []) {  // 내부 hook 단위 dedupe (순서 보존)
>       const k = [h.type, h.command, h.timeout].join("\u0000");
>       if (!tgt.hooks.some(x => [x.type, x.command, x.timeout].join("\u0000") === k)) tgt.hooks.push(h);
>     }
>   }
>   merged.hooks[ev] = [...groups.values()];
> }
> fs.writeFileSync(process.argv[3], JSON.stringify(merged, null, 2));
> ' "$SETTINGS" "$PATCH" "$SETTINGS.new" && mv "$SETTINGS.new" "$SETTINGS"
> ```

복잡 시 fallback (manual merge 안내):

```
사용자 ~/.claude/settings.json 가 비어있거나 thiscode hook 만 등록 시:
- 위 PATCH 를 그대로 settings.json 으로 작성

기존 hook 있는 경우:
- 사용자 ~/.claude/settings.json 열기
- "hooks" 키 안에 SessionStart + UserPromptSubmit 추가 (기존 항목 뒤에 append)
```

### Step 4. 검증

```bash
# JSON 유효성
python3 -m json.tool "$SETTINGS" >/dev/null && echo "✅ JSON valid"

# 등록된 hook 확인
python3 -c '
import json
with open("'"$SETTINGS"'") as f: d = json.load(f)
hooks = d.get("hooks", {})
print("SessionStart hooks:", len(hooks.get("SessionStart", [])))
print("UserPromptSubmit hooks:", len(hooks.get("UserPromptSubmit", [])))
print("Stop hooks:", len(hooks.get("Stop", [])))
'
```

### Step 5. 새 세션에서 효과 확인

```bash
# 기존 claude 세션 종료
exit

# 새 세션 시작
claude
```

→ SessionStart hook 이 첫 응답 직전 stdout 으로 soul.md / 메모리 / 공통 규율 inject. 사용자가 첫 메시지 보내면 4-gate self-check 표 stdout 주입.

확인: 첫 응답에서 봇이 페르소나 어휘 + 시그니처 사용 → ✅

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

- hooks 본문: [../hooks/bot-session-init.sh](../hooks/bot-session-init.sh) / [discord-slash-cmd.sh](../hooks/discord-slash-cmd.sh) / [regression-self-check.sh](../hooks/regression-self-check.sh) / [stop-debug-surface.sh](../hooks/stop-debug-surface.sh) (opt-in)
- active meeting Stop reread(선택): [../hooks/meeting-stop-reread.sh](../hooks/meeting-stop-reread.sh) — bot session + active meeting + non-recursive Stop 일 때만 `{"decision":"block","reason":<재독 지시>}` (Stop 엔 hookSpecificOutput 변형 없음), 그 외 fail-open(빈 stdout + exit 0).
- DISCORD_STATE_DIR 구조: [../templates/discord-state-dir-README.md](../templates/discord-state-dir-README.md)
- 첫 봇 생성: [create-bot.md](create-bot.md)
- 메인 wizard: [start.md](start.md)
