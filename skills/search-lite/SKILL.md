---
name: search-lite
description: Use when searching the vault in a minimal or distributed environment without GraphRAG — Obsidian CLI / MCP / Grep 3-Tier cascade.
allowedTools: Bash, Read, Glob, Grep, mcp__obsidian__*
---

# /search-lite — vault 통합 검색 (경량 배포용)

$ARGUMENTS

> **이 커맨드는 GraphRAG 서버를 사용하지 않습니다.** 로컬에 Python uvicorn 서버나 KuzuDB가 없어도 동작합니다.
> 풀스펙 버전(`/search`)는 GraphRAG 하이브리드 검색을 사용하며 별도 인프라가 필요합니다.
> 배포·최소 환경용 버전이 이 `/search-lite`입니다.

<routing>
## Phase 0: 모드 결정

query = "$ARGUMENTS"

IF query가 비어있으면:
  → "사용법: `/search-lite <질문>` or `/search-lite --deep <질문>`"
  → "예시: `/search-lite MCP란?` | `/search-lite --deep 프롬프트 엔지니어링 기법 비교`"
  → 종료

### 플래그 파싱
- `--quick` 또는 `-q` → **QUICK** (플래그 제거 후 나머지가 query)
- `--deep` 또는 `-d` → **DEEP** (플래그 제거 후 나머지가 query)
- 플래그 없음 → **AUTO**

### AUTO 라우팅

DEEP: 문장형 5단어+, "~하려면/방법/비교/차이/관계/영향", 분석 요청("설명해줘/정리해줘"), 복수 개념("A vs B"), 방법론("어떻게/왜")
QUICK: 그 외 (키워드 1-3개, 정의형 "~란?", 노트 찾기)
</routing>

<vault_path>
## Vault 경로 결정

우선순위:
1. 환경변수 `OBSIDIAN_VAULT_PATH` 설정 시 사용
2. CLAUDE.md 프로젝트 컨텍스트에 명시된 vault 경로
3. 현재 작업 디렉토리가 `.obsidian/` 폴더를 포함하면 그것이 vault root
4. 상위 디렉토리 탐색 (최대 3레벨 위까지) — `.obsidian/` 감지

모두 실패 시:
→ "vault 경로를 찾을 수 없습니다. 환경변수 OBSIDIAN_VAULT_PATH를 설정하거나, vault 폴더 안에서 실행해주세요."
→ 종료
</vault_path>

<search_engine>
## 공통 검색 엔진 — 3-Tier Cascade (GraphRAG 미사용)

### Tier 1 — Obsidian CLI (우선, 설치되어 있을 경우)

```bash
# Windows(WSL 포함)
"/mnt/c/Program Files/Obsidian/Obsidian.com" search "${QUERY}" --vault "${VAULT_NAME}" --format json 2>/dev/null

# macOS
open "obsidian://search?vault=${VAULT_NAME}&query=${QUERY_ENCODED}"

# 검색 결과 JSON 파싱 → 상위 N개 추출
```

CLI 부재 또는 exit 255(알려진 버그) 시 → Tier 2로 폴백.

### Tier 2 — Obsidian MCP (CLI 실패 시)

```
mcp__obsidian__simple_search({
  query: "${QUERY}",
  context_length: 100
})
```

MCP 서버 미연결 시 → Tier 3로 폴백.

### Tier 3 — Grep 직접 검색 (비상 폴백)

```bash
# vault 전체 grep
grep -rn "${QUERY}" "${VAULT_PATH}" --include="*.md" 2>/dev/null | head -50

# 또는 frontmatter tag 검색
grep -rln "^tags:.*${TAG}" "${VAULT_PATH}" --include="*.md"
```

### 모드별 파라미터
- **QUICK**: 상위 5개 결과, 노트 읽기 1-2개
- **DEEP**: 상위 10개 결과, 노트 읽기 3-5개
</search_engine>

<quick_mode>
## QUICK 모드 — 즉답 (3-5줄)

### 노트 읽기
검색 결과 상위 1-2개의 파일을 Read:
- vault 루트 기준 상대 경로로 접근
- frontmatter + 첫 문단/핵심 섹션만 추출

### 출력
```
**답변:**
[3~5줄 직접 답변. 노트 내용 기반.]

**근거 노트:**
1. **[노트 제목]** — [핵심 한 줄] (`경로`)
2. **[노트 제목]** — [핵심 한 줄] (`경로`)
```
</quick_mode>

<deep_mode>
## DEEP 모드 — 상세 분석

### 노트 읽기 (CRITICAL)
검색 결과 상위 3-5개의 파일을 실제 Read:
- 각 노트에서 제목, 요약, 핵심 섹션 추출
- 여러 노트 내용을 종합

### 답변 합성
읽은 노트 내용을 종합하여 **질문에 직접 답변**. 번호 목록, 테이블, 단계별 설명 활용.

### 출력
```
## {질문 요약}

{답변 본문. 구조화된 분석.}

### 출처
1. [[노트1]] — {핵심 정보 1줄} (`경로`)
2. [[노트2]] — {핵심 정보 1줄} (`경로`)
3. [[노트3]] — {핵심 정보 1줄} (`경로`)
```
</deep_mode>

<constraints>
## 제약

- **읽기 전용**: 노트 생성/수정 금지
- **hallucination 금지**: 반드시 실제 노트 내용 기반
- **노트에 없는 내용**: "vault에 관련 자료가 없습니다" 명시
- **출처 필수**: 실제 읽은 노트 경로 표기
- **질문/스킬/에이전트 스폰 금지**: 직접 검색만 수행
- **상태 메시지 금지**: 바로 결과 출력
- Read 실패 시 건너뛰고 다음 노트 시도
- QUICK: 5줄 이내 + 출처 1-2개
- DEEP: 제한 없음 + 출처 3-5개

### 결과 없음
```
vault에서 "{query}" 관련 자료를 찾지 못했습니다.
/knowledge-manager-lite로 자료를 수집해보세요.
```
</constraints>

<differences_from_full_search>
## /search-lite 와 /search 차이점

| 항목 | /search (풀스펙) | /search-lite (경량) |
|------|-----------------|-------------------|
| 엔진 | GraphRAG 하이브리드 (Dense+Sparse+Entity+Decomposed) | Obsidian CLI/MCP/Grep 3-Tier |
| 의존성 | Python uvicorn(8400), KuzuDB, embedding index | Obsidian 또는 grep만 |
| 정확도 | 높음 (의미 기반 + 엔티티 그래프) | 중간 (텍스트 매칭 기반) |
| 속도 | 100-500ms (서버 warm 시) | 50-300ms (vault 크기에 따라) |
| 설치 | .team-os/graphrag 필요 + 일일 빌드 cron | 설치 불필요 (Obsidian/grep만) |
| 권장 환경 | 연구/창작/분석 | **배포·개인 PC 최소 환경** |
</differences_from_full_search>

---

## Auto-Learned Patterns

- [2026-04-12] 배포 환경에서 GraphRAG 서버 의존성 없는 경량 검색 커맨드를 `/search`에서 분리 생성 — 3-Tier Cascade(Obsidian CLI → MCP → Grep) 구조로 설치 없이 동작. `/search`와 동일한 QUICK/DEEP/AUTO 라우팅 유지 (source: 2026-04-12-0021)

---

## How to Use This Skill

Use this skill for lightweight, headless vault search without interactive mode selection. Pass `--quick` or `--deep` for immediate mode choice. Ideal for automated queries and non-interactive environments.
