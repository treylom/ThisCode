---
name: knowledge-manager-at
description: Use when the user asks to organize or save knowledge into the vault and Agent Teams is available — full parallel KM (Category Lead + RALPH workers + DA cross-check).
allowedTools: Task, Read, Write, Bash, Glob, Grep, mcp__obsidian__*, mcp__notion__*, mcp__playwright__*, mcp__hyperbrowser__*, WebFetch, AskUserQuestion, TeamCreate, TeamDelete, TaskCreate, TaskUpdate, TaskList, TaskGet, SendMessage
---

> **Contracts**: `.claude/reference/contracts/{km-mode-spec, km-variant-matrix}.md` v0.1.0. Mode I/R/G + variant 책임 경계는 본 contracts 와 일치해야 함.

# Knowledge Manager - Agent Teams 호출

> **이 명령어는 풀스케일 Agent Teams(9명)를 자동 구성합니다.**
> 단일 에이전트 버전: `/knowledge-manager` (Agent Teams 미지원 환경용)
> 에이전트 정의: `.claude/agents/knowledge-manager-at.md` 참조
> 공유 사양: `.claude/agents/knowledge-manager.md` 참조

---

## 팀 아키텍처 요약

```
Lead (Main) - Opus 1M
 +-- vault-intel-lead (Sonnet 1M) — Category Lead
 |    +-- @graph-navigator (Sonnet 1M, Explore)
 |    +-- @retrieval-specialist (Sonnet 1M, Explore)
 |    +-- @link-curator (Haiku, Explore)
 +-- content-proc-lead (Sonnet 1M) — Category Lead
 |    +-- @content-extractor (Sonnet 1M, general-purpose)
 |    +-- @deep-reader (Sonnet 1M, Explore)
 |    +-- @content-analyzer (Sonnet 1M, general-purpose)
 +-- @devils-advocate (Sonnet 1M) — DA
```

---

## STEP 0: 환경 확인 (가장 먼저 실행!)

**환경 확인 후 Agent Office URL을 사용자에게 항상 표시합니다.**

### 0-0. Agent Office 대시보드 부트스트랩 (간소화 — ensure-server.sh)

**단일 스크립트로 서버 확인 + 자동 시작을 처리합니다.**

```
# === Agent Office 경로 감지 (2단계) ===
1. Glob("**/agent-office/ensure-server.sh") → 찾으면 agent_office_path = dirname 결과
2. Glob("agent-office/server.js") → 찾으면 agent_office_path = "agent-office"
3. 모두 실패 → agent_office_path = null

# === 대시보드 자동 실행 (한 줄 — CRITICAL) ===

IF agent_office_path != null:
  Bash("bash {agent_office_path}/ensure-server.sh $(pwd)")
  dashboard_available = (exit code == 0)

  # 브라우저 자동 오픈 (WSL 환경 대응)
  Bash("cmd.exe /c start http://localhost:3747 2>/dev/null || open http://localhost:3747 2>/dev/null || xdg-open http://localhost:3747 2>/dev/null || true")

  # URL 항상 표시 (자동 오픈 성공 여부 무관 — CRITICAL)
  "Agent Office 대시보드: http://localhost:3747"

  # WSL/tmux 환경 수동 접근 안내
  IF env_platform == "wsl":
    "tmux 세션에서 브라우저가 자동으로 열리지 않을 수 있습니다."
    "Windows 브라우저에서 직접 http://localhost:3747 을 열어주세요."

ELSE:
  dashboard_available = false
  "Agent Office 미설치. 대시보드 없이 진행."
```

### 0-1. .team-os/ 인프라 확인 (크로스 플랫폼)

```
# Step 1: 프로젝트 루트 절대 경로 획득
Bash("pwd") → {project_root}

# Step 2: 절대 경로로 Glob (WSL 상대 경로 실패 방지)
Glob("{project_root}/.team-os/registry.yaml") → 존재하면 Team OS 활성화
Glob("{project_root}/.team-os/spawn-prompts/*.md") → Spawn Prompt 사용 가능 여부

# Step 3: Glob 빈 결과 시 Bash 폴백
Bash("ls -la .team-os/registry.yaml 2>/dev/null && echo EXISTS || echo NOT_FOUND")
Bash("ls .team-os/spawn-prompts/*.md 2>/dev/null | wc -l")
```

### 0-2. Obsidian 환경 확인 (3-Tier)

```bash
OBSIDIAN_CLI="/mnt/c/Program Files/Obsidian/Obsidian.com"

# Tier 1: CLI 확인 (우선)
"$OBSIDIAN_CLI" version 2>/dev/null
→ 응답 있으면: obsidian_method = "cli"

# Tier 2: CLI 실패 시 MCP 확인
mcp__obsidian__list_notes({}) → 응답 여부
→ 응답 있으면: obsidian_method = "mcp"

# Tier 3: 둘 다 실패 → obsidian_method = "filesystem"
```

> 팀원 에이전트 스폰 시 `obsidian_method` 값을 컨텍스트로 전달

### 0-3. tmux 확인

```
Bash("which tmux && echo AVAILABLE || echo NOT_FOUND")

tmux 없으면:
  → 사용자에게 안내: "Agent Teams는 tmux가 필요합니다. /knowledge-manager (단일 에이전트 버전)을 사용해주세요."
  → 중단
```

---

## STEP 0.5: 모드 감지 (Mode Detection)

**STEP 1 진행 전에 사용자 요청을 분석하여 모드를 결정합니다.**

| 사용자 표현 | 모드 |
|------------|------|
| URL, "정리해줘", "분석해줘", 외부 콘텐츠 | **Mode I** (Content Ingestion) — 기존 워크플로우 |
| "아카이브 정리", "카테고리 재편", "일괄 링크", "대규모 재편" | **Mode R** (Archive Reorganization) |
| 기존 vault 폴더 50+ 파일 지칭 | **Mode R 제안** (사용자에게 확인) |
| "그래프 구축", "GraphRAG", "지식그래프", "인사이트 분석", "커뮤니티 탐색", "그래프 업데이트", "프론트매터 동기화" | **Mode G** (GraphRAG) |

### Mode R 팀 아키텍처 (AT 버전)

```
Mode R Team:
Lead (Opus 1M) — 전체 조율 + 모든 파일 쓰기 (Python 배치 직접 실행)
├── analyst-1..N (Sonnet 1M, Explore) — Phase R1 병렬 분석
│   - 파일 수에 따라 2-5개 스폰
│   - Progressive Reading (frontmatter + 첫 5줄)
│   - 산출물: topic_clusters, series, reply_chains, hubs, cross_links
├── @devils-advocate (Sonnet 1M) — Phase R2/R3 규칙 검증
│   - CATEGORY_DESIGN.md 검증
│   - {TARGET}_RULES.md 검증
│   - CONCERN → 수정 → ACCEPTABLE (최대 3회)
└── [쓰기 워커 없음 — Lead가 Python으로 직접 실행]
    - CRITICAL: worktree 버그로 팀원 쓰기 위임 금지
    - Lead가 apply_footers.py, update_mocs.py 등 직접 생성+실행
```

### Mode R 감지 시 분기

```
Mode R 선택 시:
→ km-archive-reorganization.md 스킬의 Phase R0-R5 실행
→ 아래 STEP 1-6 (Mode I) 대신 Mode R 워크플로우
→ 팀 구성: analyst-1..N + DA (쓰기 워커 없음)

Mode R 추가 질문: 대상 폴더, 재편 범위, auto-commit 여부
(상세: km-archive-reorganization.md 사전 질문 섹션 참조)
```

### Mode G 팀 아키텍처 (AT 버전)

```
Mode G Team:
Lead (Opus 1M)
├── graph-build-lead (Sonnet 1M, Category Lead)
│   ├── @ontology-designer (Sonnet 1M, Explore)
│   ├── @entity-extractor (Sonnet 1M, Explore)
│   └── @community-analyst (Sonnet 1M, Explore)
├── graph-query-lead (Sonnet 1M, Category Lead)
│   ├── @insight-researcher (Sonnet 1M, Explore)
│   └── @panorama-scanner (Sonnet 1M, Explore)
└── @devils-advocate (Sonnet 1M)
```

### Mode G 감지 시 분기

```
Mode G 선택 시:
→ km-graphrag-workflow.md 스킬의 Phase G0-G6 실행
→ 아래 STEP 1-6 (Mode I) 대신 Mode G 워크플로우
→ 팀 구성: graph-build-lead + graph-query-lead + DA

Mode G phases: G0(delta) → G1(온톨로지) → G2(엔티티 추출) → G3(관계 구축) →
              G4(커뮤니티 탐지) → G5(인사이트 분석) → G6(frontmatter 동기화)
```

**Mode I 선택 시** → 아래 STEP 1부터 기존 워크플로우 계속.

---

## STEP 1: 사용자 선호도 확인 (필수!)

**콘텐츠 처리/읽기 전에 반드시 AskUserQuestion을 호출하세요!**
**4개 질문을 한 번의 호출로 모두 물어봅니다!**

```json
AskUserQuestion({
  "questions": [
    {
      "question": "콘텐츠를 얼마나 상세하게 정리할까요?",
      "header": "상세 수준",
      "options": [
        {"label": "요약 (1-2p)", "description": "핵심만 간략히"},
        {"label": "보통 (3-5p)", "description": "주요 내용 + 약간의 설명"},
        {"label": "상세 (5p+) (권장)", "description": "모든 내용을 꼼꼼히"}
      ],
      "multiSelect": false
    },
    {
      "question": "어떤 영역에 중점을 둘까요?",
      "header": "중점 영역",
      "options": [
        {"label": "전체 균형 (권장)", "description": "모든 영역을 균형있게"},
        {"label": "개념/이론", "description": "핵심 아이디어와 원리"},
        {"label": "실용/활용", "description": "사용법, 예시, 튜토리얼"},
        {"label": "기술/코드", "description": "구현, 아키텍처, 코드"}
      ],
      "multiSelect": false
    },
    {
      "question": "노트를 어떻게 분할할까요?",
      "header": "노트 분할",
      "options": [
        {"label": "단일 노트", "description": "모든 내용을 하나의 노트에"},
        {"label": "주제별 분할", "description": "주요 주제마다 별도 노트 (MOC 포함)"},
        {"label": "원자적 분할", "description": "최대한 작은 단위로 분할 (Zettelkasten)"},
        {"label": "3-tier 계층 (권장)", "description": "메인MOC + 카테고리MOC + 원자노트"}
      ],
      "multiSelect": false
    },
    {
      "question": "기존 노트와 얼마나 연결할까요?",
      "header": "연결 수준",
      "options": [
        {"label": "최소", "description": "태그만 추가"},
        {"label": "보통", "description": "태그 + 관련 노트 링크 제안"},
        {"label": "최대 (권장)", "description": "태그 + 링크 + 기존 노트와 자동 연결 탐색"}
      ],
      "multiSelect": false
    }
  ]
})
```

> AT 버전에서는 RALPH가 항상 ON (max 5회), DA가 항상 ON입니다.
> 별도 질문 없이 자동 적용됩니다.

> **퀵 프리셋은 `/knowledge-manager-m` 전용입니다.** 이 커맨드에서는 항상 STEP 1 질문을 수행합니다.

---

## STEP 1.5A: 이미지 자동 추출 (질문 없이 항상 실행)

> **이미지 추출은 사용자가 명시적으로 "텍스트만"이라고 말하지 않는 한 항상 자동 실행됩니다.**

### 이미지 추출 자동 판별

| 소스 유형 | image_extraction | 근거 |
|----------|-----------------|------|
| 웹 URL (일반) | **auto** (모든 콘텐츠 이미지, 최대 15개) | 기본 활성화 |
| PDF | **auto** (모든 콘텐츠 이미지, 최대 15개) | 기본 활성화 |
| 소셜 미디어 | **auto** (본문 이미지, 최대 10개) | 기본 활성화 |
| Vault 종합 | **auto** (기존 Resources/images 참조 + 누락 이미지 보완) | 기본 활성화 |
| 사용자 "이미지도", "이미지 포함" | **true** (전체, 제한 없음) | 명시적 확장 |
| 사용자 "텍스트만", "이미지 제외" | **false** | 명시적 제외 (유일한 비활성 조건) |

**자동 실행 동작:**
- `image_extraction_enabled = true` (기본값)
- content-extractor에게 Image Catalog 생성 지시 자동 포함
- Phase 5.25 (이미지 저장 및 임베딩) 항상 활성화
- 참조 스킬: `km-image-pipeline.md`

---

## STEP 1.5B: PDF 처리 방식 확인 (PDF인 경우만!)

PDF 파일이 입력된 경우에만 이 질문을 합니다:

```json
AskUserQuestion({
  "questions": [
    {
      "question": "대용량 PDF입니까? /pdf 스킬로 처리하시겠습니까?",
      "header": "PDF 처리",
      "options": [
        {"label": "아니오 (기본)", "description": "Read로 직접 읽기 시도"},
        {"label": "예", "description": "/pdf 스킬로 전체 변환 후 처리"}
      ],
      "multiSelect": false
    }
  ]
})
```

---

## STEP 2~4: 팀 구성 → 스폰 → 결과 수집 (RALPH · DA)

See `references/` for detailed procedures only when the matched step asks for them.

> **전체 절차 = [references/team-pipeline.md](references/team-pipeline.md) Read 후 수행** (팀 9-spec · 병렬 스폰 · RALPH 루프 · DA cross-check · 대시보드). progressive disclosure.

## STEP 5~6: 노트 생성 → 이미지 → 연결 강화 → 보고

> **전체 절차 = [references/store-finalize.md](references/store-finalize.md) Read 후 수행** (STEP5 노트생성 · 5.25 이미지 임베딩 · STEP6 연결강화·팀정리 · 처리결과 보고 템플릿 · 참조 스킬 표).

## 사용자 요청 내용

$ARGUMENTS

---

## How to Use This Skill

Use this skill for large-scale vault reorganization tasks (archive cleanup, category restructuring, bulk linking, insight generation). This variant (AT mode) uses Agent Teams for parallel processing. Recommend when managing 500+ notes or performing complex graph operations.
