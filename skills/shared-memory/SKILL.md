---
name: shared-memory
description: Use when designing or migrating shared memory across bots and machines. Defines the 4-tier policy (T1 git-tracked shared / T2 machine-specific / T3 project-meetings / T4 per-bot WD) and Read-before-Edit + concurrent-write safety patterns derived from the vault SHARED-INDEX.md model.
license: MIT
compatibility: Obsidian vault 사용자 + plain markdown folder 사용자 양쪽 호환
metadata:
  author: treylom
  version: "0.1.0"
  hermes:
    tags: [Memory, BotOrchestration]
---

# shared-memory

> **사용 시점**: 봇 2개 이상 운영 + 머신 1개 이상 + 회의 진행 시. 공유 메모리를 어디 두고 누가 쓰는지 결정해야 할 때.

## 4-tier 정책 (vault SHARED-INDEX.md 기반)

| Tier | 위치 (Obsidian vault 가정) | 위치 (plain markdown 가정) | 누가 쓰나 |
|---|---|---|---|
| **T1 — git-tracked shared** | `<vault>/.claude-memory/shared/` | `<repo>/shared-memory/` | 모든 봇·머신. cross-bot leak 인정 사실 |
| **T2 — machine-specific** | `<vault>/.claude-memory/machine-mac/` 또는 `machine-wsl/` | `<repo>/machine-<host>/` | 해당 머신만. 경로·하드웨어 의존 |
| **T3 — project-meetings** | `<vault>/.claude-meetings/<YYYY-MM-DD>-<topic>/` | `<repo>/meetings/<YYYY-MM-DD>-<topic>/` | 회의 audience 봇들 (in-flight, 영구 기록) |
| **T4 — per-bot WD** | `~/.claude/projects/<encoded-WD>/memory/` | 동일 | 그 봇만 (개성·실수 복기, git untracked) |

## T1 — 공유 메모리

### 구조

```
shared/
├── SHARED-INDEX.md              # 인덱스 (한 줄씩 link)
├── feedback_<topic>.md          # 봇 간 합의된 운영 규율
├── project_<name>.md            # 현재 진행 프로젝트 상태
├── reference_<topic>.md         # 외부 시스템 reference
└── design_<topic>.md            # 시스템 토폴로지·설계
```

### SHARED-INDEX.md 형식

```markdown
# Cross-Bot Memory Index

## Feedback (운영 규율)
- [<짧은 설명>](feedback_xxx.md) — 한 줄 요약

## Project (진행 상태)
- [<프로젝트>](project_xxx.md) — 현재 상태

## Reference (외부 시스템)
- [<reference>](reference_xxx.md) — 한 줄 요약
```

세션 시작 시 본 인덱스를 로드 → 필요한 항목만 fetch (full file 읽기).

### Read-before-Edit 규칙

같은 파일을 두 봇이 동시 edit 시 충돌. 안전 패턴:
1. **Read 먼저** (always)
2. **Edit 시 base SHA 확인** (git pull --rebase 후 작업)
3. **Append-only 우선** (한 줄 추가는 충돌 risk 최소)
4. **Lock 필요 시** (`.lock` 파일 또는 `flock`)

## T2 — 머신 특화

```
machine-mac/
├── MAC-INDEX.md
├── env-paths.md                  # /opt/homebrew/... 같은 머신 path
└── hardware-spec.md
```

cross-machine sync 시 본 폴더는 제외 (rsync exclude pattern).

## T3 — 회의실 (project-meetings)

meetings skill 의 4-file 표준 적용. 자세히는 그 skill 참조.

## T4 — per-bot WD memory

```
~/.claude/projects/<encoded-WD>/memory/
├── MEMORY.md                     # WD memory 인덱스
├── feedback_<topic>.md
└── ...
```

`<encoded-WD>` 는 Claude Code 가 자동 encoding (예: `<vault>` → `<encoded-WD>`).

SessionStart hook 으로 본 인덱스 자동 주입.

## 분기 기준 — 어디에 쓸 지

```
사실 / 결정 사항
  ├─ 모든 봇 + 모든 머신 공유? ──→ T1 shared/
  ├─ 본 머신만 의존? ─────────→ T2 machine-<host>/
  ├─ 회의 in-flight? ───────────→ T3 meetings/<topic>/
  └─ 봇 자기 개성·실수 복기? ──→ T4 per-bot WD memory
```

## 사용자 vault 없는 경우 — plain folder fallback

본 plugin 의 wizard 가 사용자에게 묻기:

```
공유 메모리 위치:
(A) Obsidian vault 안 (`.claude-memory/shared/`)
(B) 별도 git 레포 폴더 (`shared-memory/`)
(C) 사용 안 함 (per-bot WD 만)
```

(A) 가 default — 사용자 vault 가 있다면. (B) 가 fallback — 사용자가 Obsidian 안 쓰는 경우.

## 트러블슈팅

| 증상 | 원인 | 대응 |
|---|---|---|
| 같은 fact 가 두 봇에서 충돌 작성 | T1 동시 edit | git pull --rebase + append-only 우선 |
| WD memory 안 보임 | SessionStart hook 미설정 | `~/.claude/settings.json` hooks 등록 확인 |
| 머신 sync 시 secrets 노출 | T2 에 `.env` 들어감 | `.gitignore` 에 `.env` 등록 + 신규 발급 권장 |

## 관련 자원

- 한국어 가이드: [../../docs/03-shared-memory.md](../../docs/03-shared-memory.md)
- vault SHARED-INDEX 실 예시: `<vault>/.claude-memory/shared/SHARED-INDEX.md`
- 회의실 skill: [../meetings/SKILL.md](../meetings/SKILL.md)

---

## How to Use This Skill

Use this skill to manage cross-machine, cross-bot shared memory. Handles memory index management, bot-specific vs. shared memory separation, and memory synchronization across multiple machines (Mac/WSL).
