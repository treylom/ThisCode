# 03. 공유 메모리 — 4-tier 시스템

> 봇 N 개 + 머신 M 개 + 회의 K 개를 운영하면서 "어디에 무엇을 쓰는지" 가 가장 큰 결정. thiscode 의 공유 메모리 시스템은 vault SHARED-INDEX.md 패턴 일반화.

## 왜 분리하는가

봇이 1개일 때는 모든 사실을 한 파일에 써도 OK. 봇이 2개 이상 + 머신 2개 이상이 되는 순간 **충돌 / 누락 / 의도된 격리** 가 동시에 발생:

- 봇 A 의 개성·실수 복기를 봇 B 가 읽으면 페르소나 leak
- 머신 1 의 path (`/opt/homebrew/...`) 를 머신 2 가 읽으면 broken
- 회의 in-flight 결정을 다른 봇이 잘못 읽으면 회의 결론 변경

→ Tier 분리 필요.

## 4-tier 표

| Tier | 위치 | 누가 쓰나 | 누가 읽나 | git 추적 |
|---|---|---|---|---|
| **T1 — shared** | `<vault>/.claude-memory/shared/` | 모든 봇 + 머신 | 모든 봇 + 머신 | ✅ |
| **T2 — machine-specific** | `<vault>/.claude-memory/machine-<host>/` | 해당 머신 봇만 | 해당 머신 봇만 | ✅ |
| **T3 — project-meetings** | `<vault>/.claude-meetings/<topic>/` | 회의 audience | 회의 audience + 후속 작업자 | ✅ |
| **T4 — per-bot WD** | `~/.claude/projects/<encoded>/memory/` | 해당 봇만 | 해당 봇만 | ❌ (machine local) |

## 분기 기준

```
지금 쓰려는 사실 / 결정 / 학습:

1) 다른 봇이나 머신이 읽어야 하는가? 
   YES → T1 또는 T2 또는 T3 (아래 계속)
   NO  → T4 (per-bot WD)

2) 머신 의존 정보인가? (경로 / IP / 하드웨어 사양)
   YES → T2 (machine-specific)
   NO  → 계속

3) 회의 in-flight 인가? (audience 봇 ≥2)
   YES → T3 (meetings/<topic>/)
   NO  → T1 (shared/)
```

## T1 — shared/ 구조

```
shared/
├── SHARED-INDEX.md              # 모든 항목 인덱스 (세션 시작 시 자동 로드)
├── feedback_<topic>.md          # 운영 규율 (사용자 정정 + Why + How to apply)
├── project_<name>.md            # 진행 프로젝트 상태
├── reference_<topic>.md         # 외부 시스템 reference
└── design_<topic>.md            # 시스템 토폴로지·설계
```

### feedback 메모리 anatomy

```markdown
---
name: feedback-xxx
description: 한 줄 요약
type: feedback
scope: shared
---

# 규율

규율 본문 (1-3 줄)

**Why**: 왜 이 규율이 필요한가 (과거 회귀 사례 또는 사용자 정정 인용)
**How to apply**: 언제 / 어떻게 적용하는지
```

## T2 — machine-specific 활용

```
machine-mac/
├── MAC-INDEX.md
├── env-paths.md            # /opt/homebrew/bin/claude 등
└── hardware-spec.md        # M4 / 32GB / ...

machine-wsl/
├── WSL-INDEX.md
├── env-paths.md            # <vault> 등
└── hardware-spec.md
```

cross-machine sync 시 본 폴더는 exclude.

## T3 — meetings/ 

자세히는 [05-회의실.md] 참조. 4-file 표준 (00-context / 01-spec / 02-progress / 03-outcome).

## T4 — per-bot WD memory

```
~/.claude/projects/-Users-<user>-<encoded-WD>/memory/
├── MEMORY.md                # 인덱스 (Claude Code SessionStart 자동 주입)
├── feedback_<bot>_<topic>.md
└── ...
```

봇 specific 페르소나 정정 (예: "orchestrator-bot 이 특정 단어 반복 회귀") 본 위치.

## 사용자 vault 없는 경우 (plain markdown 만)

wizard 가 묻기:

```
Q: 공유 메모리 위치 어떻게 하실래요?
  (A) Obsidian vault 안 (.claude-memory/shared/)
  (B) 별도 git 레포 폴더 (shared-memory/)
  (C) 사용 안 함 (per-bot WD T4 만)
```

- (A) — vault 사용자 default
- (B) — vault 안 쓰지만 멀티 머신 sync 필요
- (C) — 단일 머신 + 단일 봇

## SessionStart hook 자동 주입

`~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "cat <vault>/.claude-memory/shared/SHARED-INDEX.md 2>/dev/null"
          }
        ]
      }
    ]
  }
}
```

세션 시작 시 SHARED-INDEX 자동 주입 → agent 가 인식.

## 트러블슈팅

| 증상 | 원인 | 대응 |
|---|---|---|
| 같은 fact 두 봇에서 동시 작성 → git merge 충돌 | T1 동시 edit | git pull --rebase + append-only 우선 |
| WD memory 안 보임 | SessionStart hook 미설정 | settings.json hooks 등록 |
| machine-specific 가 cross-machine sync 시 broken | T2 폴더 미exclude | rsync exclude pattern + `.gitignore` |
| 회의 outcome 이 shared 로 leak | T3 → T1 잘못 이동 | T3 에 보존, summary 만 T1 (selective) |

## 관련 자원

- skill: [../skills/shared-memory/SKILL.md](../skills/shared-memory/SKILL.md)
- 회의실: [05-meeting-thread-protocol.md] (예정)
- vault 실 예시: `<vault>/.claude-memory/shared/SHARED-INDEX.md`
