---
name: knowledge-manager
description: Use when the user asks to organize or save researched content into the Obsidian vault in an environment without Agent Teams — single-agent sequential KM pipeline (extract → analyze → structure → store → link).
allowedTools: Read, Write, Bash, Glob, Grep, mcp__obsidian__*, mcp__notion__*, mcp__playwright__*, mcp__hyperbrowser__*, WebFetch, AskUserQuestion
---

> **Contracts**: `.claude/reference/contracts/{km-mode-spec, km-variant-matrix}.md` v0.1.0. Mode I/R/G + variant 책임 경계는 본 contracts 와 일치해야 함.

# Knowledge Manager 호출 (단일 에이전트)

> **이 명령어는 단일 에이전트가 모든 작업을 순차적으로 직접 수행합니다.**
> Agent Teams 풀스케일 버전: `/knowledge-manager-at` (tmux + .team-os 필요)
> 에이전트 정의: `.claude/agents/knowledge-manager.md` 참조
> **⚡ Orchestrator Pipeline**: `km-karpathy-pipeline.md` — Linting + Filed Back + Q&A 오버레이

---

## 아키텍처

```
Main (Opus 1M, 단일 세션) — Karpathy 7-Layer Fusion
 └── Phase 0: /using-superpowers 게이트 + 환경 감지 + 모드/선호도
 └── Phase 1: DATA INGEST — 콘텐츠 추출
 └── Phase 2: EXTRA TOOLS — Vault 탐색 + GraphRAG (Mode I에서도 항상)
 └── Phase 3: COMPILE — raw→wiki 컴파일 + Q&A 양방향 [NEW]
 └── Phase 4: LINTING — /autoresearch 지식 Health Check [NEW]
 └── Phase 5: KNOWLEDGE STORE — 저장 + 연결 강화 + Cross-phase 검증
 └── Phase 6: OUTPUTS + FILED BACK — 산출 + Wiki 환류 [NEW]
```

**어디서든 동작** (tmux 없어도, Agent Teams 없어도, VS Code/SDK에서도).

---

## STEP 0: 스킬 게이트 + 환경 확인

> **⚠️ MANDATORY: 아래 두 스킬을 반드시 호출한 후 진행.**

### 0-PRE. 필수 스킬 활성화 (생략 금지)

```
MUST: Skill("/using-superpowers") 호출
  → 적용 가능 스킬 목록 식별, 작업 순서에 매핑
  → 이 호출 없이 STEP 1 이후 진행 금지

참조: km-karpathy-pipeline.md (Orchestrator Pipeline 오버레이)
  → STEP 4.5에서 /autoresearch 패턴 적용 (lint 루프)
```

### 0-0. 환경 확인 (간소화)

**사용자에게 표시할 필요 없음. 내부적으로 판단만 수행.**

### Obsidian 접근 방식 확인 (3-Tier)

```bash
OBSIDIAN_CLI="/mnt/c/Program Files/Obsidian/Obsidian.com"

# Tier 1: CLI 확인 (우선)
"$OBSIDIAN_CLI" version 2>/dev/null
→ 응답 있으면: obsidian_method = "cli"

# Tier 2: CLI 실패 시 MCP 확인
mcp__obsidian__list_notes({}) → 응답 여부
→ 응답 있으면: obsidian_method = "mcp"

# Tier 3: 둘 다 실패 시
→ obsidian_method = "filesystem"
→ Write/Read/Grep 도구로 직접 파일 저장
```

### 0-1. 파이프라인 상태 초기화 (HARD GATE)

```
Bash("python3 agent-office/km-tools/km-tools.py state init")
→ JSON 응답에서 session_id 확인
→ 이후 모든 STEP 완료 시 state complete 호출 필수:
  Bash("python3 agent-office/km-tools/km-tools.py state complete STEP-N")
→ error 응답(STEP_SKIP_DETECTED) 시 즉시 중단, 누락된 STEP 실행
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

### Mode R 감지 시

```
사용자 요청이 Mode R에 해당합니다.
대규모 vault 재편 모드(Mode R)로 진행할까요?

Mode R은 다음을 수행합니다:
- Phase R0: 사전 정리 (merge conflict, dead link, 레거시 폴더)
- Phase R1: Progressive Reading + 분석
- Phase R2: 카테고리 설계 + DA 검증
- Phase R3: 규칙서 생성 + DA 검증
- Phase R4: Python 배치 실행
- Phase R5: 검증 + 보고

참조 스킬: km-archive-reorganization.md
```

**Mode R 선택 시** → `km-archive-reorganization.md` 스킬의 Phase R0-R5 실행. 아래 STEP 1-6 대신 Mode R 워크플로우를 따릅니다.

**Mode R 추가 질문:**

```json
AskUserQuestion({
  "questions": [
    {
      "question": "재편 대상 폴더와 범위를 알려주세요.",
      "header": "대상 폴더",
      "options": [
        {"label": "특정 폴더", "description": "vault 내 특정 폴더 지정"},
        {"label": "전체 vault", "description": "vault 전체 재편"}
      ]
    },
    {
      "question": "어떤 재편을 원하시나요?",
      "header": "재편 범위",
      "options": [
        {"label": "카테고리 재분류", "description": "파일을 새 카테고리로 재배치"},
        {"label": "링크 강화", "description": "기존 구조 유지, 교차 링크만 추가"},
        {"label": "풀 재편", "description": "카테고리 + 링크 + MOC + 시리즈 전체"}
      ]
    },
    {
      "question": "매 배치 후 auto-commit 할까요?",
      "header": "Auto-commit",
      "options": [
        {"label": "예 (권장)", "description": "매 Python 배치 후 즉시 commit+push (auto-sync 경합 방지)"},
        {"label": "아니오", "description": "모든 작업 완료 후 한 번에 커밋"}
      ]
    }
  ]
})
```

### Mode G 감지 시

```
사용자 요청이 Mode G에 해당합니다.
그래프 구축 모드(Mode G)로 진행할까요?

Mode G는 다음을 수행합니다:
- Phase G0: Delta 감지 (frontmatter_hash 비교, 변경 노트 확인)
- Phase G1: 온톨로지 설계 (엔티티 타입, 관계 타입 정의)
- Phase G2: 엔티티 추출 (노트 → 그래프 엔티티 변환)
- Phase G3: 관계 구축 (엔티티 간 typed 관계 생성)
- Phase G4: 커뮤니티 탐지 (클러스터링, 커뮤니티 ID 부여)
- Phase G5: 인사이트 분석 (커뮤니티 요약, 글로벌 인사이트)
- Phase G6: Frontmatter 동기화 (graph_entity/community/connections 갱신)

참조 스킬: km-graphrag-workflow.md
```

**Mode G 선택 시** → `km-graphrag-workflow.md` 스킬의 Phase G0-G6 실행. 아래 STEP 1-6 대신 Mode G 워크플로우를 따릅니다.

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

> 단일 에이전트 버전에서는 RALPH/DA 관련 질문이 없습니다 (미사용).

### 이미지 추출 판별 (키워드 감지 시에만 활성화)

| 사용자 표현 | image_extraction | 근거 |
|------------|-----------------|------|
| "이미지", "이미지도", "이미지 포함" | **true** (모든 콘텐츠 이미지, 최대 15개) | 명시적 요청 |
| "그래프", "차트", "다이어그램", "그래프 포함" | **auto** (차트/다이어그램만, 최대 10개) | 시각 자료 요청 |
| "텍스트만", "이미지 제외" | **false** | 명시적 제외 |
| (키워드 없음) | **false** | 기본값 — 텍스트만 추출 |

> **이미지 추출은 사용자가 관련 키워드를 명시할 때만 활성화됩니다.**
> `/knowledge-manager-at`은 항상 자동 추출합니다.
> 참조 스킬: `km-image-pipeline.md`

> **퀵 프리셋은 `/knowledge-manager-m` 전용입니다.** 이 커맨드에서는 항상 STEP 1 질문을 수행합니다.

---

## STEP 1.5: PDF 처리 방식 확인 (PDF인 경우만!)

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

- **"아니오"** → Read로 직접 읽기
- **"예"** → `marker_single "파일.pdf" --output_format markdown --output_dir ./km-temp`

---

## STEP 2: 콘텐츠 추출 (Main 직접)

Main이 입력 소스를 직접 추출합니다. 스킬 참조: `km-content-extraction.md`, `km-youtube-transcript.md`, `km-social-media.md`

### 소스 유형별 추출

| 입력 유형 | 추출 방법 |
|----------|----------|
| **YouTube** | `youtube-transcript-api` → `yt-dlp` 폴백 → 스킬: `km-youtube-transcript.md` |
| **소셜 미디어 (Threads/Instagram)** | `playwright-cli open → snapshot` ⭐ **1순위** (scrapling은 첫 포스트만 반환, SNS에서 MCP 사용 금지) |
| **일반 웹 URL** | `scrapling-crawl.py --mode dynamic` (1순위) → `--mode stealth` (2순위) → `playwright-cli` (3순위) → `WebFetch` (정적) |
| **PDF (작은)** | Read 직접 시도 (< 5MB, < 20p) |
| **PDF (큰)** | /pdf 스킬 또는 marker_single |
| **DOCX/XLSX/PPTX** | Read 또는 해당 스킬 도구 |
| **Notion URL** | mcp__notion__API-get-block-children |
| **Vault 종합 ("종합해줘")** | CLI: `"$OBSIDIAN_CLI" search` + 순차 `read` / MCP 폴백: search_vault + read_multiple_notes |

### 증분 처리 — 중복 소스 감지 + 변경점 자동 추출 (Incremental Processing)

> **Karpathy 원칙: "새 소스가 도착하면 LLM이 읽고, 핵심 정보를 추출하고, 기존 위키에 통합한다."**
> 단순히 "있는지 없는지"만 보는 게 아니라, **"뭐가 바뀌었는지"까지 자동으로 추출**해야 한다.

```
추출 완료 직후, vault에 동일 소스가 이미 존재하는지 확인:

1. 소스 감지 (3단계 탐색):
   a) URL 매칭: Grep("source: {추출된_URL}", vault_path)
   b) 제목/키워드 매칭: CLI: "$OBSIDIAN_CLI" search query="{소스 제목}" format=json
   c) 폴더 매칭: 소스명에서 프로젝트명 추출 → vault 내 동명 폴더 탐색
      (예: "CC101" → Library/Research/CC101-Guide/ 폴더 발견)

2. 판정:
   - 기존 노트 없음 → 신규 처리 (기존 흐름 계속)
   - 기존 노트 발견 → 사용자에게 질문:
     "이 소스는 이미 처리된 적이 있습니다: {기존_노트_경로}
      1) 업데이트 (변경점 추출 → 기존 노트에 반영)
      2) 새로 생성 (별도 노트로 생성)
      3) 스킵 (처리 중단)"

3. 업데이트 모드 — 변경점 자동 추출 (km-tools diff):
   a) 기존 노트를 임시 파일로 저장, 새 추출 콘텐츠도 임시 파일로 저장
   b) km-tools diff 실행:
      Bash("python3 agent-office/km-tools/km-tools.py diff {existing_tmp} {new_tmp}")
      → JSON 응답의 sections 배열: NEW/CHANGED/REMOVED/RENAMED 자동 분류
      → markdown 필드: "## 변경점 요약" 섹션 텍스트 (draft에 직접 삽입 가능)
   c) 변경점 분류 (km-tools가 자동 수행):
      - [NEW] 새로 추가된 섹션/콘텐츠
      - [CHANGED] 내용이 수정된 섹션 (유사도 점수 포함)
      - [REMOVED] 삭제된 섹션
      - [RENAMED] 이름/번호가 변경된 섹션
   d) 변경점 요약을 STEP 4로 전달 (draft에 "## 변경점 요약" 섹션 자동 생성)
```

### 추출 결과 정리

```
추출 완료 후 다음 정보를 정리:
- 제목, 저자, 날짜
- 전체 콘텐츠 (Markdown)
- 섹션 구조
- 미디어/이미지 URL
- 인용/참조
- [증분 모드 시] 기존 노트 대비 변경된 부분만 표시
```

### 이미지 URL 수집 (image_extraction != false 일 때)

콘텐츠 추출과 **동시에** 이미지 정보도 수집합니다:

```
1. 웹 URL: browser_snapshot에서 img/figure 요소의 src, alt, 주변 heading 수집
   - 필터링: km-image-pipeline.md 기준 (< 100x100px 제외, 광고 도메인 제외)
   - auto 모드: 차트/다이어그램만 (우선순위 1-2), 최대 10개
   - 차트/그래프 감지: canvas/SVG → browser_take_screenshot
2. PDF: marker 출력의 images/ 폴더 스캔
3. 수집 결과를 메모리에 보관 (별도 파일 불필요):
   collected_images = [
     { type: "chart", url: "...", context: "...", placement: "..." },
     ...
   ]
```

> 참조 스킬: `km-content-extraction.md` 2F, `km-image-pipeline.md`

---

## STEP 3: Vault 탐색 (Main 직접 - 순차)

See `references/` for detailed procedures only when the matched step asks for them.

> **전체 절차 = [references/vault-search.md](references/vault-search.md) Read 후 수행** (Phase A 그래프 / A-G GraphRAG 하이브리드 / B 키워드 / C 교차검증). progressive disclosure.

## STEP 4~5.5: COMPILE → LINTING → STORE → PROPAGATE

> **전체 절차 = [references/steps-compile-store.md](references/steps-compile-store.md) 를 Read 후 그대로 수행** (progressive disclosure — SKILL.md ≤500).
- STEP 4 COMPILE: raw→wiki draft 생성
- STEP 4.5 LINTING: 지식 Health Check (HARD GATE — 통과 draft만 STORE)
- STEP 5 STORE: 노트 저장 (3-Tier CLI→MCP→Write)
- STEP 5.5 PROPAGATE: 기존 노트 업데이트 (Wiki Pattern)

## STEP 6: 연결 강화 + 결과 보고

### 6-1. 연결 강화 (연결 수준 "보통" 또는 "최대"일 때)

상세 워크플로우: `km-link-strengthening.md` 참조

```
1. 새 노트 핵심 키워드 추출
2. CLI `"$OBSIDIAN_CLI" search` / MCP search_vault로 관련 노트 탐색
   - CLI `"$OBSIDIAN_CLI" deadends` → 나가는 링크 없는 파일 = 연결 강화 우선 후보 (format 옵션 미지원, 플레인 텍스트 목록 반환)
3. 관련성 점수 3점 이상인 노트와 양방향 링크 생성
4. CLI `"$OBSIDIAN_CLI" append` / MCP update_note로 기존 노트에 역방향 링크 추가
   - CLI `"$OBSIDIAN_CLI" prepend` → 네비게이션 헤더 추가 시 사용
```

### 6-2. Filed Back — 환류 (Explorations add up)

> **Karpathy 핵심: "모든 탐색은 Wiki로 환류된다."**
> 이번 세션에서 생성된 산출물과 발견을 Wiki에 축적한다.

```
1. 이번 세션 산출물 목록화:
   - 생성된 노트 목록
   - STEP 4.5 lint에서 발견된 인사이트
   - STEP 4.5-1 규칙 3 "Suggest new articles" 결과

2. 환류 실행:
   - lint 과정에서 발견된 기존 노트 오류 → 해당 노트 수정
   - "Suggest new articles" 항목 → Open Questions 노트 생성
     경로: Library/Research/{프로젝트명}/Open-Questions-{날짜}.md
   - Open Questions는 다음 KM 세션의 탐색 시드가 된다

3. 환류 노트 생성 (Open Questions가 있을 때):
   ---
   title: "Open Questions — {주제}"
   tags: [status/open, research, open-questions]
   source_session: "{날짜} KM 세션"
   ---
   ## 탐색 시드 (다음 세션용)
   - [ ] {질문 1} — 출처: {관련 draft 노트}
   - [ ] {질문 2} — 출처: {lint 규칙 3에서 제안}
   - [ ] {질문 3} — 출처: {Q&A 미답변}
```

### 6-3. 결과 보고

```
## 결과 보고 · Vault 동기화 · 참조 스킬

> 상세 = [references/reporting-sync.md](references/reporting-sync.md) (결과 보고 템플릿 · STEP7 WSL→Win 동기화 · 참조 스킬 표 · Auto-Learned).

## 사용자 요청 내용

$ARGUMENTS

---

## How to Use This Skill

Use this skill for full-featured knowledge management with all interactive features — AskUserQuestion prompts, variant selection, detailed content settings. Default choice for personal vault operations with full UI/notification support.
