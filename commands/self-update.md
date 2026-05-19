---
description: thiscode 플러그인 자가 업데이트 체크 (git fetch + behind 알림) — 메인봇 SessionStart 시 자동 호출 가능
allowed-tools: Bash Read
disable-model-invocation: true
---

# /thiscode:self-update — 자가 업데이트 체크

> 메인봇 시작 시 또는 수동으로 thiscode 레포의 latest commit 과 로컬 차이를 점검.

$ARGUMENTS

---

## 진행 흐름

### Step 1. 로컬 plugin 위치 detect

```bash
# thiscode 설치 위치 자동 detect — self-update 는 git 갱신 대상이므로
# .git 보유 clone 우선. 실제 설치 위치 전부 순서대로 probe.
TARGET=""
for _cand in \
  "$HOME/.claude/plugins/marketplaces/thiscode-marketplace" \
  "$HOME/.claude/plugins/thiscode" \
  "$HOME/.claude/plugins/cache/local/thiscode" \
  "$HOME/code/thiscode"; do
  if [ -d "$_cand/.git" ]; then TARGET="$_cand"; break; fi
done

if [ -z "$TARGET" ]; then
  # git clone 아닌 cache-only 설치: 자체 git 갱신 불가 → 안내
  for _cand in \
    "$HOME/.claude/plugins/thiscode" \
    "$HOME/.claude/plugins/cache/local/thiscode" \
    "$HOME"/.claude/plugins/cache/thiscode-marketplace/thiscode/*; do
    if [ -d "$_cand" ]; then
      echo "thiscode 발견($_cand) 이나 git clone 아님 — '/plugin marketplace update' 또는 재설치 필요"
      exit 1
    fi
  done
  echo "thiscode 미설치"
  exit 1
fi
```

### Step 2. git fetch + behind 비교

```bash
cd "$TARGET"
git fetch origin --quiet
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)
BEHIND=$(git rev-list --count HEAD..origin/main)
```

### Step 3. 결과 보고

```
{
  "status": "<up-to-date|behind|ahead|diverged>",
  "local": "<short-sha>",
  "remote": "<short-sha>",
  "behind_count": <N>,
  "ahead_count": <M>,
  "last_remote_commit_subject": "<subject>",
  "last_remote_commit_date": "<ISO date>"
}
```

agent 가 사용자에게 안내:
- `up-to-date`: 조용히 종료 (변화 없음)
- `behind N`: "N 개 commit 뒤처져 있어요. `/thiscode:self-update pull` 로 업데이트 받을 수 있습니다"
- `ahead M`: 사용자가 local 수정 가지고 있음 — manual review 필요
- `diverged`: rebase 또는 reset 필요 — manual

### Step 4. (옵션) `pull` 인자 시 자동 업데이트

```bash
if [ "$ARGUMENTS" = "pull" ]; then
  cd "$TARGET"
  git pull --ff-only
  echo "업데이트 완료. 새 commit:"
  git log --oneline HEAD~"$BEHIND".."$HEAD"
  # J-2 재적용: 다봇 통신용 discord 플러그인 패치는 외부 플러그인이라
  # 업데이트로 덮어써질 수 있음. idempotent·fail-open(절대 self-update 안 깸).
  bash "$TARGET/scripts/patch-discord-bot-drop.sh" 2>&1 || true
fi
```

⚠️ `pull --ff-only` 사용 — diverged 일 때 안전 실패. local 수정 보존.
J-2 재적용 스크립트는 idempotent(이미 패치면 no-op) + fail-open(실패해도 exit 0)
이라 self-update 체인을 깨지 않는다. 상세·opt-in SessionStart 등록 = docs/08-debug-노하우.md J-2.

---

## SessionStart hook 으로 자동 호출 (선택)

⚠️ **재귀 invoke 차단** — `claude -p` 호출 X (자식 process 가 같은 settings.json 읽고 SessionStart 다시 fire → 무한 재귀 risk). 대신 bash 직접 호출로 lightweight behind-count 만.

`~/.claude/settings.json` 또는 `<vault>/.claude/settings.json` 의 hook 등록:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "cd $HOME/.claude/plugins/cache/local/thiscode 2>/dev/null && git fetch --quiet origin 2>/dev/null && BEHIND=$(git rev-list HEAD..origin/main --count 2>/dev/null) && [ \"${BEHIND:-0}\" -gt 0 ] && echo \"⚠ thiscode behind by $BEHIND commits — /thiscode:self-update 실행 권장\" || true",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

→ 매 세션 시작 시 자동 update check (bash 직접, claude 재귀 invoke 회피). behind 시만 stdout 알림 — claude 가 본 알림을 attention pool 에 흡수. `/thiscode:self-update` 는 사용자 명시 호출 (`disable-model-invocation: true`).

---

## 검증

- [ ] up-to-date 상태일 때 silent 종료
- [ ] behind 상태일 때 N 개 commit 정보 정확 표시
- [ ] `pull` 인자 시 `--ff-only` 동작 (diverged 안전 실패)
- [ ] SessionStart hook 등록 시 매 세션 자동 체크
