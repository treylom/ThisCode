---
description: thiscode 의 SessionStart + UserPromptSubmit hooks 를 ~/.claude/settings.json 에 안전 merge (기존 hook 보존)
allowed-tools: Bash Read Write Edit AskUserQuestion
disable-model-invocation: true
---

# /thiscode:install-hooks — hook 등록

> 순정 Claude Code 에서 soul.md / WD memory / 슬래시 detect / 회귀 self-check 자동 작동을 위해 hooks 를 `~/.claude/settings.json` 에 등록. 기존 사용자 hook 보존 (jq merge).

$ARGUMENTS

---

## 등록할 hooks 3개

1. **SessionStart** → `bot-session-init.sh`
   - soul.md (페르소나) 자동 inject
   - WD memory 인덱스 자동 inject
   - 공통 규율 (페르소나·슬래시·메모리 분기) inject

2. **UserPromptSubmit** → `discord-slash-cmd.sh`
   - 프롬프트 첫 줄 `/cmd` 매칭 → Skill 도구 invoke 강제

3. **UserPromptSubmit** → `regression-self-check.sh`
   - 4-gate self-check (Discord reply / 단정 표현 / single-grep / skill invoke) 매 응답 전 환기

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
          }
        ]
      }
    ]
  }
}
EOF
)

# 기존 hook 보존 + thiscode hook append
jq -s '.[0] * .[1] | .hooks.SessionStart = ((.[0].hooks.SessionStart // []) + (.[1].hooks.SessionStart // []) | unique_by(.hooks[0].command)) | .hooks.UserPromptSubmit = ((.[0].hooks.UserPromptSubmit // []) + (.[1].hooks.UserPromptSubmit // []) | unique_by(.hooks[0].command))' \
  "$SETTINGS" <(echo "$PATCH") > "$SETTINGS.tmp"
mv "$SETTINGS.tmp" "$SETTINGS"
```

⚠️ jq merge 정확성 보장 — agent 가 사용자 기존 settings.json 의 hook 들을 보존하면서 thiscode hook 만 추가.

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
| `jq: command not found` | jq 미설치 | `brew install jq` (Mac) / `apt install jq` (Linux) |
| SessionStart hook 작동 안 함 | settings.json 의 `hooks.SessionStart[].matcher` 가 다른 값 | matcher: "" (전체 match) 확인 |
| soul.md 안 inject | DISCORD_STATE_DIR 미설정 | claude 시동 시 `export DISCORD_STATE_DIR="$HOME/.claude/channels/discord-<bot-name>"` 명시 |
| 사용자 기존 hook 충돌 | jq merge unique_by 가 같은 command 매칭 못 함 | manual 검토 |

---

## 관련 자원

- hooks 본문: [../hooks/bot-session-init.sh](../hooks/bot-session-init.sh) / [discord-slash-cmd.sh](../hooks/discord-slash-cmd.sh) / [regression-self-check.sh](../hooks/regression-self-check.sh)
- DISCORD_STATE_DIR 구조: [../templates/discord-state-dir-README.md](../templates/discord-state-dir-README.md)
- 첫 봇 생성: [create-bot.md](create-bot.md)
- 메인 wizard: [start.md](start.md)
