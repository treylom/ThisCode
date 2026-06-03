---
name: search
description: Use when the user asks to search the vault or find notes by concept — GraphRAG-backed unified search with quick (direct answer) or deep (analysis) depth.
allowedTools: Bash, Read, Glob, Grep
---

> **Contract**: `.claude/reference/contracts/search-fallback-4tier.md` v0.1.0. Tier 순서·인터페이스는 본 contract 와 일치해야 함. drift 감지: `~/code/thiscode/scripts/km-version.sh`.

# /search — vault 통합 검색

$ARGUMENTS

<routing>
## Phase 0: 모드 결정

query = "$ARGUMENTS"

IF query가 비어있으면:
  → "사용법: `/search <질문>` or `/search --deep <질문>`"
  → "예시: `/search MCP란?` | `/search --deep 프롬프트 엔지니어링 기법 비교`"
  → 종료

### 플래그 파싱
- `--quick` 또는 `-q` → **QUICK** (플래그 제거 후 나머지가 query)
- `--deep` 또는 `-d` → **DEEP** (플래그 제거 후 나머지가 query)
- 플래그 없음 → **AUTO**

### AUTO 라우팅

DEEP: 문장형 5단어+, "~하려면/방법/비교/차이/관계/영향", 분석 요청("설명해줘/정리해줘"), 복수 개념("A vs B"), 방법론("어떻게/왜")
QUICK: 그 외 (키워드 1-3개, 정의형 "~란?", 노트 찾기)
</routing>

<moc_priority>
## Phase 0.5: MOC 우선 라우팅 (공통 — 2026-04-21 운영 규율)

**"상위 MOC부터 보도록."** 검색 결과 중 MOC 성격 노트를 최상위로 고정한다.

### MOC 판별
다음 중 하나라도 참이면 MOC로 간주:
- frontmatter `type` 값에 `MOC` 포함 (예: `MOC`, `author-hub-MOC`, `series-category-MOC`)
- frontmatter `tags:`에 `MOC` 또는 `MOC/*` 포함
- 파일명에 `-MOC` 포함

판별 Bash (각 source_note에 대해):
```bash
grep -lE '^type:.*-?MOC|^\s*-\s*MOC\b|MOC/' "{source_note}" 2>/dev/null || \
  basename "{source_note}" | grep -qE '\-MOC'
```

### 재정렬 규칙
1. 검색 결과를 MOC / 원자 노트로 분류
2. 상위 **최대 3개 MOC를 맨 위로 고정** (score 순)
3. 원자 노트는 그 아래, 기존 점수 순 유지
4. 표시: `📌 상위 MOC (N)` 섹션 + `📄 원자 노트 (N)` 섹션 분리

### Why
- 운영 규율(2026-04-21): 문서가 많아질수록 원자 나열은 찾기·업데이트 어려움 → MOC가 허브·진입점 역할
- MOC를 먼저 보면 해당 주제의 카테고리·관련 시리즈를 한눈에 파악 가능

### 플래그
- `--no-moc` → MOC 제외, 원자 전용 모드 (Phase 0 플래그 파싱에 추가)
- MOC 0개 시 `📌` 섹션 생략 (자동)
</moc_priority>

<search_engine>
## 공통 검색 엔진 — GraphRAG → Obsidian CLI fallback (QUICK/DEEP 동일)

내용 recall 기본값은 GraphRAG입니다. GraphRAG가 불가하거나 실패하면 Obsidian CLI full-text를 2순위 안전망으로 사용합니다. CLI는 파일명·frontmatter·본문·wikilink를 찾지만 relevance ranking이 약하므로 흔한 질의는 `limit=1000`까지 확장합니다.

### 1차 — FastAPI 서버 (port 8400):
```bash
QUERY_ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "${QUERY}")
curl -s "http://127.0.0.1:8400/api/search?q=${QUERY_ENCODED}&top_k=${TOP_K}&mode=hybrid&dense_weight=0.3&sparse_weight=0.4&decomposed_weight=0.15&entity_weight=0.15" --connect-timeout 3
```

### 2차 — Obsidian CLI fallback (GraphRAG 불가·실패 시):
```bash
OBSIDIAN_CLI="/Applications/Obsidian.app/Contents/MacOS/obsidian-cli"
"$OBSIDIAN_CLI" search query="${QUERY}" format=json limit=1000
```

### 3차 — GraphRAG CLI fallback (FastAPI만 불가 시):
```bash
# repo root 및 python 실행기 자동 감지 (Mac venv 우선, 없으면 시스템 python3)
for REPO_ROOT in <vault> <vault>; do
  [ -d "$REPO_ROOT/.team-os/graphrag/scripts" ] && break
done
PY="python3"
[ -x "$REPO_ROOT/.team-os/graphrag/.venv/bin/python" ] && PY="$REPO_ROOT/.team-os/graphrag/.venv/bin/python"
cd "$REPO_ROOT" && PYTHONPATH=".team-os/graphrag/scripts" "$PY" .team-os/graphrag/scripts/graph_search.py hybrid "${QUERY}" --rerank --top-k ${TOP_K} --json 2>/dev/null
```

### 4차 — 비상 폴백:
vault-search MCP → Grep 순서로 폴백. 이 경우 답변에 "GraphRAG 서버 미실행으로 텍스트 검색 결과입니다" 명시.

### 모드별 파라미터
- **QUICK**: top_k=5, 노트 읽기 1-2개
- **DEEP**: top_k=10, 노트 읽기 3-5개
</search_engine>

<quick_mode>
## QUICK 모드 — 즉답 (3-5줄)

### 노트 읽기
검색 결과 상위 1-2개의 source_note만 Read:
- vault 경로 (Mac): `<vault>/{source_note}`
- vault 경로 (WSL): `<vault>/{source_note}`
- 실패 시 repo 경로 시도: Mac `<vault>/AI_Second_Brain/{source_note}` · WSL `<vault>/{source_note}`
- frontmatter + 첫 문단/핵심 섹션만 추출

### 출력
```
**답변:**
[3~5줄 직접 답변. 노트 내용 기반.]

📌 **상위 MOC** (N) — Phase 0.5 재정렬 반영
1. **[[MOC 제목]]** — [범위·역할 한 줄] (`경로`)

📄 **원자 노트** (N)
1. **[노트 제목]** — [핵심 한 줄] (`경로`)
2. **[노트 제목]** — [핵심 한 줄] (`경로`)
```

> MOC 0개 시 `📌` 섹션 생략. `--no-moc` 플래그 시 MOC 제외.
</quick_mode>

<deep_mode>
## DEEP 모드 — 상세 분석

### 노트 읽기 (CRITICAL)
검색 결과 상위 3-5개의 source_note를 실제 Read:
- vault 경로 (Mac): `<vault>/{source_note}`
- vault 경로 (WSL): `<vault>/{source_note}`
- 실패 시 repo 경로 시도: Mac `<vault>/AI_Second_Brain/{source_note}` · WSL `<vault>/{source_note}`
- 각 노트에서 제목, 요약, 핵심 섹션 추출

### 답변 합성
읽은 노트 내용을 종합하여 **질문에 직접 답변**. 번호 목록, 테이블, 단계별 설명 활용.

### 출력
```
## {질문 요약}

{답변 본문. 구조화된 분석.}

### 📌 상위 MOC (진입점) — Phase 0.5 재정렬 반영
1. [[MOC1]] — {범위·역할 1줄} (`경로`)

### 📄 원자 노트 (출처)
1. [[노트1]] — {핵심 정보 1줄} (`경로`)
2. [[노트2]] — {핵심 정보 1줄} (`경로`)
3. [[노트3]] — {핵심 정보 1줄} (`경로`)
```

> MOC 0개 시 `📌` 섹션 생략. `--no-moc` 플래그 시 MOC 제외.
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
/knowledge-manager로 자료를 수집해보세요.
```
</constraints>

---

## How to Use This Skill

Use this skill for intelligent vault search with automatic mode selection (quick/deep). Supports 4-tier fallback (GraphRAG → Obsidian CLI → vault-search MCP → ripgrep), MOC prioritization, and flexible query depth. Main entry point for vault queries.
