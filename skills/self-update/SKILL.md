---
name: self-update
description: thiscode 플러그인 자가 업데이트 체크 (git fetch + behind 알림) — 메인봇 SessionStart 시 자동 호출 가능
disable-model-invocation: true
allowed-tools: Bash Read
---

사용자가 이 스킬을 호출했다 — 아래 단계를 순서대로 지금 수행한다.

# /thiscode:self-update — 자가 업데이트 체크

> 메인봇 시작 시 또는 수동으로 thiscode 레포의 latest commit 과 로컬 차이를 점검.

$ARGUMENTS

---

## 진행 흐름

### Step 0. 로드 실체 판별 — git pull 성공 ≠ 표면 갱신 (2026-08-09 WSL 실측)

Claude Code 가 마켓플레이스로 설치된 플러그인을 로드하는 곳은 **버전 고정 사본**
(`~/.claude/plugins/cache/<마켓플레이스>/thiscode/<버전>/`, `.git` 없음)이다.
git 체크아웃을 아무리 당겨도 이 사본은 안 바뀐다. 실측된 3겹 함정:
① git pull "성공" → 표면 불변 ② `plugin marketplace update` "성공" → 플러그인 불변
③ `plugin update thiscode` → `not found` 실패. **유일하게 통하는 형태 =
`claude plugin update thiscode@<마켓플레이스>`** (1.0.0→1.2.1 갱신 실측 — **수동 터미널 실행 기준**.
세션 내 자동 실행은 편의 경로라 오래 멈추면 중단하고 같은 명령을 터미널에서 직접 친다).

```bash
INSTALL_KIND="git-checkout"; UPDATE_CMD=""; CACHE_VERS=""
for _c in "$HOME"/.claude/plugins/cache/*/thiscode/*/; do
  [ -d "$_c" ] || continue
  [ -d "$_c/.git" ] && continue
  _mkt=$(basename "$(dirname "$(dirname "$_c")")")
  INSTALL_KIND="marketplace-cache"
  UPDATE_CMD="claude plugin update thiscode@${_mkt}"
  CACHE_VERS="$CACHE_VERS$(basename "$_c") "
done
echo "install_kind=$INSTALL_KIND ${UPDATE_CMD:+update_cmd=$UPDATE_CMD }${CACHE_VERS:+cache_versions=$CACHE_VERS}"
```

버전 폴더 목록(`cache_versions`)이 갱신 판정의 **before 기준선**이다 — "새 명령이 보이는가"는
before 없이는 답할 수 없는 질문이라, 판정은 사람 눈이 아니라 파일시스템(버전 폴더 증감)이 한다.

### Step 1. 로컬 plugin 위치 detect

```bash
# thiscode 설치 위치 자동 detect — self-update 는 git 갱신 대상이므로
# .git 보유 clone 우선. 실제 설치 위치 전부 순서대로 probe.
# 마켓플레이스 이름은 설치처마다 다름(예: tofukyung-plugins — 2026-07-22 실측) — 고정명 ❌, glob probe.
TARGET=""
for _cand in \
  "$HOME/.claude/plugins/marketplaces/"* \
  "$HOME/.claude/plugins/thiscode" \
  "$HOME/.claude/plugins/cache/local/thiscode" \
  "$HOME/code/thiscode" \
  "$HOME/code/ThisCode"; do
  [ -d "$_cand/.git" ] || continue
  # 소속 확인 필수 — marketplaces/* 글롭은 «남의» 마켓플레이스도 훑는다. 첫 .git 에서
  # 무조건 break = 첫 매치 미끼(2026-08-09 WSL 실측: claude-dashboard 오탐 TARGET,
  # 마켓 9중 8이 .git 보유라 거의 확정 발생). origin 이 thiscode 일 때만 채택 —
  # Step 2 의 `git fetch origin` 이 origin 을 요구하므로 remote 없는 clone 제외도 정합.
  git -C "$_cand" remote get-url origin 2>/dev/null | grep -qi thiscode || continue
  TARGET="$_cand"
  break
done

if [ -z "$TARGET" ]; then
  # git clone 아닌 cache-only 설치: 자체 git 갱신 불가 → 안내
  for _cand in \
    "$HOME/.claude/plugins/thiscode" \
    "$HOME/.claude/plugins/cache/local/thiscode" \
    "$HOME"/.claude/plugins/cache/thiscode-marketplace/thiscode/*; do
    if [ -d "$_cand" ]; then
      echo "thiscode 발견($_cand) 이나 git clone 아님 — 갱신 명령: ${UPDATE_CMD:-claude plugin update thiscode@<마켓플레이스>}"
      echo "(marketplace update 만으론 플러그인이 안 바뀐다 — 2026-08-09 실측)"
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
# 기본 브랜치 main 고정 가정 ❌ (main/master 혼재 — 2026-07-22 tofukyung-plugins=master 실측)
DEF=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || echo "origin/main")
git rev-parse --verify --quiet "$DEF" >/dev/null || DEF="origin/master"
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "$DEF")
BEHIND=$(git rev-list --count "HEAD..$DEF")
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

보고에 `install_kind` 를 반드시 포함한다 (`marketplace-cache` | `git-checkout`).

agent 가 사용자에게 안내:
- `up-to-date`: 조용히 종료 (변화 없음)
- `behind N` + `git-checkout`: "N 개 commit 뒤처져 있어요. `/thiscode:self-update pull` 로 업데이트 받을 수 있습니다"
- `behind N` + `marketplace-cache`: "git 사본은 N 개 뒤처져 있고, **실제 로드되는 설치본은 별도 사본**이에요. 갱신은 `<UPDATE_CMD>` 한 줄 + Claude Code 재시작입니다" — **git 숫자만 보여주고 pull 을 처방하지 마라 (거짓 성공 함정)**
- `ahead M`: 사용자가 local 수정 가지고 있음 — manual review 필요
- `diverged`: rebase 또는 reset 필요 — manual

### Step 4. (옵션) `pull` 인자 시 자동 업데이트

```bash
if [ "$ARGUMENTS" = "pull" ]; then
  cd "$TARGET"
  git pull --ff-only
  # J-2 재적용: 다봇 통신용 discord 플러그인 패치는 외부 플러그인이라
  # 업데이트로 덮어써질 수 있음. idempotent·fail-open(절대 self-update 안 깸).
  bash "$TARGET/scripts/patch-discord-bot-drop.sh" 2>&1 || true

  # ⚠ Step 0 재도출 — Claude Code 의 Bash 호출은 블록마다 별개 프로세스라
  # 셸 변수가 계승되지 않는다(2026-08-09 글재경 R1: 미계승 시 조용히 else 로
  # 떨어져 하필 "업데이트 완료"에 착지 — fail-open 방향 교정 포함).
  INSTALL_KIND="git-checkout"; UPDATE_CMD=""; VERS_BEFORE=""
  for _c in "$HOME"/.claude/plugins/cache/*/thiscode/*/; do
    [ -d "$_c" ] || continue
    [ -d "$_c/.git" ] && continue
    _mkt=$(basename "$(dirname "$(dirname "$_c")")")
    INSTALL_KIND="marketplace-cache"
    UPDATE_CMD="claude plugin update thiscode@${_mkt}"
    VERS_BEFORE="$VERS_BEFORE$(basename "$_c") "
  done

  if [ "$INSTALL_KIND" != "git-checkout" ]; then
    # 미확정 포함 전부 이 정직 경로로 (백스톱: 조건을 뒤집어 fail-open = 정직 쪽)
    echo "git 사본 갱신 완료 — 로드되는 설치본 갱신 실행: $UPDATE_CMD (현재 버전 폴더: $VERS_BEFORE)"
    # 수동 터미널 실측(1.0.0→1.2.1) 기준 — 세션 내 자동 실행은 편의 경로. 갱신은 새 버전
    # 폴더를 «추가»하고 실행 중 구버전 폴더는 존치한다(실측: 1.2.1/ 신규 생성·1.0.0 유지).
    claude plugin update "thiscode@${_mkt}" || echo "자동 실행 실패 — 터미널에서 직접 실행하세요: $UPDATE_CMD"
    VERS_AFTER=""
    for _c in "$HOME"/.claude/plugins/cache/*/thiscode/*/; do
      [ -d "$_c" ] || continue
      [ -d "$_c/.git" ] && continue
      VERS_AFTER="$VERS_AFTER$(basename "$_c") "
    done
    if [ "$VERS_AFTER" != "$VERS_BEFORE" ]; then
      echo "✅ 설치본 갱신 확인(파일시스템 판정): [$VERS_BEFORE] → [$VERS_AFTER] — Claude Code 재시작 후 새 명령 사용 가능"
    else
      echo "⚠ 설치본 버전 폴더 불변([$VERS_BEFORE]) — 갱신 안 됨. 직접 실행: $UPDATE_CMD"
    fi
  else
    echo "업데이트 완료. 새 commit:"
    git log --oneline HEAD~"$BEHIND".."$HEAD"
  fi
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
- [ ] **marketplace-cache 설치에서**: `install_kind` 보고 + pull 시 `plugin update thiscode@<마켓플레이스>` 실행/안내 + «재시작 후 자동완성 확인» 판정 기준 출력 — git pull 만으로 "업데이트 완료" 문구 0 (거짓 성공 차단, 2026-08-09 실측 근거)
- [ ] SessionStart hook 등록 시 매 세션 자동 체크
