---
name: knowledge-manager-lite
description: Use when running knowledge management in a minimal, distributed, or headless environment — keyword-based auto-preset, no AskUserQuestion, no kakao/mobile notifications.
allowedTools: Read, Write, Bash, Glob, Grep, mcp__obsidian__*, mcp__notion__*, mcp__playwright__*, mcp__hyperbrowser__*, WebFetch
---

> **Contracts**: `.claude/reference/contracts/{km-mode-spec, km-variant-matrix}.md` v0.1.0. Mode I/R/G + variant 책임 경계는 본 contracts 와 일치해야 함.

# Knowledge Manager Lite 호출 (경량 · 배포용)

> **이 커맨드는 키워드 기반 자동 프리셋으로 동작합니다.**
> 콘텐츠 설정(상세/중점/분할/연결)은 AskUserQuestion 없이 자동 결정됩니다.
> **카카오 전송 로직과 모바일 ntfy 알림이 제거된 배포용 버전입니다.**
> 개인용 대화형 버전: `/knowledge-manager` (전체 AskUserQuestion 사용)
> 개인용 모바일/카카오 연동 버전: `/knowledge-manager-m`
> 에이전트 정의: `.claude/agents/knowledge-manager.md` 참조

---

## 아키텍처

```
Main (Opus 1M, 단일 세션, AskUserQuestion 없음)
 └── 키워드 기반 자동 프리셋 → 순차 실행:
      0. 환경 확인
      0.5. 모드 감지 + 자동 프리셋 결정
      2. 콘텐츠 추출
      3. Vault 그래프 탐색
      4. 콘텐츠 분석 + 노트 구조 설계
      5. 노트 생성
      6. 연결 강화 + 결과 보고
```

**어디서든 동작** (tmux 없어도, Agent Teams 없어도, SSH/headless에서도, 공용 PC 환경에서도).

---

## STEP 0: 환경 확인 (간소화)

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

---

## STEP 0.5: 자동 프리셋 결정 (AskUserQuestion 없음)

**CRITICAL**: 이 커맨드는 AskUserQuestion을 일체 사용하지 않습니다.
모든 설정(상세/중점/분할/연결/이미지/수신자)은 $ARGUMENTS 텍스트 분석으로 자동 결정됩니다.

### 0.5-1. 모드 감지 (Mode Detection)

$ARGUMENTS 텍스트를 분석하여 모드를 자동 결정합니다.

| $ARGUMENTS 패턴 | 모드 |
|----------------|------|
| URL, "정리해줘", "분석해줘", 외부 콘텐츠 | **Mode I** (Content Ingestion) |
| "아카이브 정리", "카테고리 재편", "일괄 링크", "대규모 재편" | **Mode R** (Archive Reorganization) |
| 기존 vault 폴더명 지칭 | **Mode R** (자동 진입) |
| "그래프", "GraphRAG", "인사이트" | **Mode G** (GraphRAG) |

**Mode R 자동 파라미터 (질문 없이 기본값 적용):**

| 파라미터 | 기본값 | 오버라이드 키워드 |
|---------|--------|-----------------|
| 대상 폴더 | $ARGUMENTS에서 경로 추출 | 명시적 폴더 경로 |
| 재편 범위 | 풀 재편 | "링크만"→링크 강화, "카테고리만"→카테고리 재분류 |
| Auto-commit | 예 (매 배치 후 즉시 commit) | "커밋 안함", "no commit"→아니오 |

Mode R 선택 시 → `km-archive-reorganization.md` 스킬의 Phase R0-R5 실행.

### 0.5-2. 복합 프리셋 매칭 (최우선)

$ARGUMENTS에서 아래 키워드를 순서대로 매칭합니다. **첫 매칭이 적용됩니다.**

| $ARGUMENTS 키워드 | 상세 수준 | 중점 영역 | 노트 분할 | 연결 수준 |
|---|---|---|---|---|
| "빠르게", "간단히" | 요약 (1-2p) | 전체 균형 | 단일 노트 | 최소 |
| "요약해줘", "요약" | 요약 (1-2p) | 전체 균형 | 단일 노트 | 최대 |
| "상세하게 요약해줘", "상세 요약" | 보통 (3-5p) | 전체 균형 | 주제별 분할 | 최대 |
| "꼼꼼히", "자세히", "체계적으로" | 상세 (5p+) | 전체 균형 | 원자적 분할 | 최대 |
| "기본으로", "기본" | 상세 (5p+) | 전체 균형 | 3-tier | 최대 |
| "연구보고서", "논문정리" | 상세 (5p+) | 개념/이론 | 3-tier | 최대 |
| "실무용", "실용적으로" | 보통 (3-5p) | 실용/활용 | 주제별 분할 | 보통 |
| "레퍼런스", "참고용" | 보통 (3-5p) | 기술/코드 | 단일 노트 | 보통 |
| "공부용", "학습용" | 상세 (5p+) | 개념/이론 | 원자적 분할 | 최대 |

### 0.5-3. 개별 파라미터 오버라이드 (복합 미매칭 시)

복합 프리셋에 매칭되지 않은 경우, 개별 키워드로 각 파라미터를 결정합니다.

**상세 수준:**

| 키워드 | 값 |
|--------|---|
| "요약", "간략", "summary", "brief" | 요약 (1-2p) |
| "보통", "적당", "standard" | 보통 (3-5p) |
| "상세", "자세", "detailed", "comprehensive" | 상세 (5p+) |
| (매칭 없음) | **상세 (5p+)** |

**중점 영역:**

| 키워드 | 값 |
|--------|---|
| "실용", "활용", "사용법", "practical" | 실용/활용 |
| "이론", "개념", "concept" | 개념/이론 |
| "기술", "코드", "technical", "code" | 기술/코드 |
| "인사이트", "분석", "insight" | 인사이트 |
| (매칭 없음) | **전체 균형** |

**노트 분할 (상세 수준에 연동):**

| 키워드 | 값 |
|--------|---|
| "단일", "하나로", "single" | 단일 노트 |
| "분할", "나눠", "주제별", "2티어", "2-tier", "split" | 주제별 분할 (2-tier) |
| "원자", "zettelkasten", "atomic" | 원자적 분할 |
| "3-tier", "계층", "tier" | 3-tier 계층 |
| (매칭 없음 + 요약) | **단일 노트** |
| (매칭 없음 + 보통) | **3-tier 계층** (기본화 — 명시 선택은 항상 우선) |
| (매칭 없음 + 상세) | **3-tier 계층** |

**연결 수준:**

| 키워드 | 값 |
|--------|---|
| "연결 최소", "태그만", "minimal" | 최소 |
| "연결 보통", "moderate" | 보통 |
| (매칭 없음) | **최대** |

### 0.5-4. 부가 옵션 자동 판별

**이미지 추출:**

| 키워드 | 값 |
|--------|---|
| "이미지도", "이미지 포함", "차트 포함", "그래프 포함", "images" | **true** |
| "텍스트만", "이미지 빼고", "text only" | **false** |
| (매칭 없음) | **false** (기본값 — 텍스트만 추출) |

**PDF 처리 (PDF 입력 시만):**

```
PDF 파일 감지 시:
  → 파일 크기 > 5MB 또는 페이지 수 > 20 → marker_single (중량 처리)
  → 그 외 → Read 도구 직접 읽기 (경량 처리)
질문 없이 자동 분기합니다.
```

### 0.5-5. 프리셋 결과 출력 (필수!)

자동 결정 완료 후 **반드시** 다음 테이블을 사용자에게 출력합니다 (확인용, 블로킹 아님):

```
**자동 프리셋 적용 결과:**

| 항목 | 설정값 | 감지 키워드 |
|------|--------|-----------|
| 모드 | {Mode I / Mode R / Mode G} | {감지 근거} |
| 상세 수준 | {값} | {매칭 키워드 또는 "기본값"} |
| 중점 영역 | {값} | {매칭 키워드 또는 "기본값"} |
| 노트 분할 | {값} | {매칭 키워드 또는 "기본값"} |
| 연결 수준 | {값} | {매칭 키워드 또는 "기본값"} |
| 이미지 추출 | {auto/true/false} | {매칭 키워드 또는 "기본값"} |

진행합니다...
```

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

### 이미지 URL 수집 (image_extraction != false 시)

```
콘텐츠 추출과 동시에 이미지 URL 수집 (인라인 모드):

1. browser_snapshot HTML에서 img/figure 태그 파싱
2. 필터링: < 100x100px 제외, 광고/트래커 제외, 아이콘 제외
3. 우선순위 분류:
   - auto: 차트/다이어그램/인포그래픽만 (우선순위 1-2)
   - true: 모든 콘텐츠 이미지 (우선순위 1-4)
4. 경량 제한: auto 최대 5개, true 최대 10개
5. 차트/SVG → browser_take_screenshot으로 캡처
6. 메모리 내 리스트로 보관 (Catalog 불필요)
```

### 추출 결과 정리

```
추출 완료 후 다음 정보를 정리:
- 제목, 저자, 날짜
- 전체 콘텐츠 (Markdown)
- 섹션 구조
- 미디어/이미지 URL (수집된 이미지 리스트 포함)
- 인용/참조
```

---

## STEP 3: Vault 탐색 (Main 직접 - 순차)

### Phase A: 그래프 탐색 (graph-navigator 로직)

```
1. Hub 노트 식별:
   - Grep으로 [[키워드]] 패턴 검색
     Grep({ pattern: "\\[\\[.*{키워드}.*\\]\\]", path: "{VAULT_PATH}" })
   - 가장 많이 참조되는 노트 = Hub 노트 (최소 2개 식별)

2. 1-hop 추적:
   - Hub 노트 Read → 내부의 모든 [[wikilink]] 추출
   - 각 링크된 노트의 제목, 태그, 첫 3줄 확인
   - CLI: `"$OBSIDIAN_CLI" read path="..."` / MCP: mcp__obsidian__read_note / Tier 3: Read

3. 2-hop 추적 (3-tier/원자적 선택 시):
   - 1-hop 노트들의 wikilink를 한 번 더 추적
   - 간접 연결 노트 목록 생성
```

### Phase A-G: GraphRAG 하이브리드 검색 (선택적 — DB 존재 시만)

```
VAULT_ROOT="${VAULT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
DB_PATH="${VAULT_ROOT}/.team-os/graphrag/index/vault_graph.db"

IF DB 존재:
  - GraphRAG 하이브리드 검색 수행 (search_server:app 또는 graph_search.py)
  - 결과를 Phase C 교차 검증에 포함

ELSE:
  - GraphRAG DB 미존재. Phase A-G 스킵. Phase B (키워드 검색)에만 의존.
  - 이것은 배포 환경에서 정상입니다.
```

> 배포용 경량 환경에서는 GraphRAG 미설치가 기본입니다. Phase A(wikilink 탐색) + Phase B(키워드 검색)만으로 충분히 동작합니다.

### Phase B: 키워드 검색 (retrieval-specialist 로직)

```
1. 키워드 검색:
   - CLI: `"$OBSIDIAN_CLI" search query="{핵심 키워드}" format=json limit=20`
   - MCP: `mcp__obsidian__search_vault` (컨텍스트 포함)
   - Grep: vault 전체 검색 (한국어 + 영어 키워드)
   - 결과 TOP 20 정리

2. 태그 검색:
   - CLI: `"$OBSIDIAN_CLI" tags counts sort=count format=json`
   - Grep으로 tags: 또는 #태그 패턴 검색 (폴백)

3. 폴더 기반 검색:
   - vault 내 관련 폴더 식별
   - Research/ MOC 파일 검색
   - 사용자 콘텐츠 폴더 검색
```

### Phase C: 교차 검증

```
Graph 결과 ∩ Retrieval 결과:

- 양쪽 모두 발견 → 핵심 노트 (확실히 관련) → 우선 처리
- Graph에만 있음 → 관계 기반 발견 (간접 연결) → 보조 참조
- Retrieval에만 있음 → 고립 노트 (키워드 매칭, 연결 없음) → 링크 후보

교차 검증 결과 테이블:
| Category | Count | Notes |
|----------|-------|-------|
| Core (양쪽 발견) | N | ... |
| Graph Only | N | ... |
| Retrieval Only | N | ... |
```

---

## STEP 4: 콘텐츠 분석 + 노트 구조 설계

### 4-1. 콘텐츠 분석

```
추출된 콘텐츠 + vault 탐색 결과를 종합하여:

1. 핵심 개념 추출 및 분류
2. 자동 프리셋 반영한 깊이/초점 조정
3. 기존 vault 노트와의 관계 분석
```

### 4-2. 노트 구조 설계

```
자동 프리셋 결과에 따라:

단일 노트:
  → 하나의 포괄 노트 설계

주제별 분할:
  → 주요 주제마다 별도 노트 + MOC

원자적 분할:
  → 각 개념당 1개 노트 + MOC

3-tier 계층:
  → 메인MOC + 카테고리MOC + 원자노트
  → Research/[프로젝트명]/ 디렉토리 구조
```

### 4-3. 태그 추천

```
기존 vault 태그 체계 기반:
- 상태: status/open, status/resolved
- 도메인: AI-Safety, ai-agent, MCP, claude-code
- 유형: MOC, research
```

### 4-4. 시각화 기회 감지

```
프로세스 감지 → Flowchart 제안
시스템 구조 감지 → Architecture 제안
비교 데이터 → 비교 테이블 제안
```

---

## STEP 5: 노트 생성 (Main 직접!)

**CRITICAL**: 노트 생성은 **반드시 Main이 직접** 수행합니다.

### 5-1. Obsidian 노트 생성

```
# Tier 1: CLI (우선)
"$OBSIDIAN_CLI" create path="적절한/경로/파일명.md" content="YAML frontmatter + 노트 내용"

# Tier 2: MCP (CLI 실패 시)
mcp__obsidian__create_note({
  path: "적절한/경로/파일명.md",
  content: "YAML frontmatter + 노트 내용"
})

# Tier 3: Write (MCP 실패 시)
Write({ file_path: "{vault_absolute_path}/적절한/경로/파일명.md", content: "..." })
```

**경로 규칙** (CLAUDE.md 참조):
- vault root 기준 상대 경로 사용
- 절대 경로 또는 중첩 prefix 금지

### 5-2. 3-tier 구조 (해당 시)

3-tier 선택 시 다음 순서로 생성:
1. 원자적 노트들 (각 개념당 1개)
2. 카테고리 MOC (각 챕터당 1개)
3. 메인 MOC (전체 요약 + 모든 카테고리 MOC 링크)

**모든 노트에 네비게이션 푸터 포함!** (km-export-formats.md 참조)

### 5-3. 저장 검증 (필수!)

```
모든 create_note 호출 후:
1. 응답에서 "created successfully" 확인
2. Glob으로 파일 존재 확인
3. 실패 시 Write 도구로 폴백
```

### 5-4. 이미지 저장 및 임베딩 (image_extraction != false 시)

**참조 스킬**: `km-image-pipeline.md`

```
1. Resources/images/{topic-folder}/ 디렉토리 생성
2. 수집된 이미지 다운로드 (curl → Playwright 폴백)
3. 노트 콘텐츠에 이미지 임베드 삽입 (본문 흐름 배치)
4. Glob으로 파일 존재 확인
```

**경량 제한**: auto 최대 5개, true 최대 10개, > 2MB 이미지 스킵

---

## STEP 6: 연결 강화 + 결과 보고

### 6-1. 연결 강화 (연결 수준 "보통" 또는 "최대"일 때)

상세 워크플로우: `km-link-strengthening.md` 참조

```
1. 새 노트 핵심 키워드 추출
2. CLI/MCP로 관련 노트 탐색
3. 관련성 점수 3점 이상인 노트와 양방향 링크 생성
4. 기존 노트에 역방향 링크 추가
```

### 6-2. 결과 보고

```
## 처리 결과 보고

### 입력 요약
- 소스: [URL/파일/vault종합]
- 모드: 경량 자동 프리셋 (배포용)

### 자동 프리셋
- 상세 수준: {값}
- 중점 영역: {값}
- 노트 분할: {값}
- 연결 수준: {값}

### Vault 탐색 결과
| 카테고리 | 수 | 비고 |
|----------|---|------|
| 핵심 노트 (교차검증) | N | Graph ∩ Retrieval |
| 관계 기반 발견 | N | Graph only |
| 키워드 매칭 | N | Retrieval only |

### 처리 요약
- 검색된 관련 노트: N개
- 교차 검증 핵심 노트: N개
- 생성된 노트: N개
- 추가된 양방향 링크: N개

### 이미지 처리 (image_extraction != false 시)
- 수집 이미지: N개
- 다운로드 성공: N개
- 임베딩 완료: N개
- 저장 경로: Resources/images/{topic-folder}/

### 출력 위치
| 노트 | 경로 | 상태 |
|------|------|------|
| [MOC명] | Research/... | 성공 |
| ... | ... | ... |
```

---

## 사용자 요청 내용

$ARGUMENTS

---

## 참조

See `references/` for detailed procedures only when the matched step asks for them.

- 사용 예시 · KM 변종 비교 · 참조 스킬 · Auto-Learned Patterns: [references/usage.md](references/usage.md)

---

## How to Use This Skill

Use this skill for lightweight, headless knowledge management — no interactive prompts, no notifications. Ideal for automated pipelines, distributed environments, and CLI-only setups. Ingest URLs, text, or reorganize vault structure with automatic preset detection.
