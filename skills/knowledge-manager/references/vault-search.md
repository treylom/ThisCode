# knowledge-manager — STEP 3 Vault 탐색 상세 (Phase A / A-G / B / C)

> SKILL.md 에서 분리(Skills 2.0 ≤500). STEP 3 실행 시 본 파일 Read 후 그대로 수행.

## STEP 3: Vault 탐색 (Main 직접 - 순차)

### Phase A0: MOC 우선 탐색 (2026-04-21 운영 규율)

> **"상위 MOC부터 보도록."** 원자 노트보다 상위 MOC를 먼저 식별해
> (1) 기존 카테고리 파악 + (2) 새 노트의 parent 후보 선확정.

```
1. MOC 후보군 수집 (vault 전역):
   - Grep frontmatter type: `grep -rlE '^type:.*-?MOC' {vault_path}/Library/`
   - Grep tags MOC: `grep -rlE '^\s*-\s*MOC\b|MOC/' {vault_path}/Library/`
   - 파일명 규칙: find "{vault_path}/Library/" -name "*-MOC*.md"

2. 관련도 점수 계산 (각 후보 MOC에 대해):
   - 작성자 일치 (MOC.author == 새 콘텐츠 author) → +3
   - 태그 교집합 → +2 per tag
   - 주제 키워드 부분 일치 → +1

3. 상위 5개 MOC를 `candidate_parent_mocs`에 저장
   → STEP 4.5 lint 규칙 4(connections) + STEP 5-0-PLUS + STEP 5.5-0에서 활용
```

### Phase A: 그래프 탐색 (graph-navigator 로직)

```
1. Hub 노트 식별:
   - Grep으로 [[키워드]] 패턴 검색
     Grep({ pattern: "\\[\\[.*{키워드}.*\\]\\]", path: "<vault>" })
   - 가장 많이 참조되는 노트 = Hub 노트 (최소 2개 식별)

2. 1-hop 추적:
   - Hub 노트 Read → 내부의 모든 [[wikilink]] 추출
   - 각 링크된 노트의 제목, 태그, 첫 3줄 확인
   - CLI: `"$OBSIDIAN_CLI" read path="..."` / MCP: mcp__obsidian__read_note / Tier 3: Read

3. 2-hop 추적 (3-tier/원자적 선택 시):
   - 1-hop 노트들의 wikilink를 한 번 더 추적
   - 간접 연결 노트 목록 생성
```

### Phase A-G: GraphRAG 하이브리드 검색 (Dense + Sparse + Reranker)

> **⚡ Mode I에서도 항상 실행.** GraphRAG 검색은 Mode G 전용이 아니다.
> Orchestrator 원칙: "Search/CLI tools는 모든 컴파일에 참여한다."
> DB 미존재 시에만 스킵 (graceful fallback).

```
VAULT_ROOT="${VAULT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
DB_PATH="${VAULT_ROOT}/.team-os/graphrag/index/vault_graph.db"
INDEX_DIR="${VAULT_ROOT}/.team-os/graphrag/index"

IF DB 존재 (Mode I, Mode G 모두 해당):
  1. 하이브리드 검색 (Dense Embedding + FTS5 Sparse + Reranker):
     Bash("python3 .team-os/graphrag/scripts/graph_search.py hybrid '{키워드}' --top-k 20 2>/dev/null || echo '[]'")
     → JSON 결과 파싱: results[].entity, results[].source_note, results[].score, results[].source
     → 실패 시 기존 LIKE 폴백:
       Bash("python3 -c \"import sqlite3; c=sqlite3.connect('{DB_PATH}').cursor(); [print(r) for r in c.execute(\\\"SELECT name, type, description, source_note FROM entities WHERE name LIKE '%{키워드}%' OR name_ko LIKE '%{키워드}%' LIMIT 20\\\")]\"")

  2. 관계 탐색 (1-2홉):
     발견된 엔티티의 source/target 관계 조회:
     Bash("python3 -c \"import sqlite3; c=sqlite3.connect('{DB_PATH}').cursor(); [print(r) for r in c.execute(\\\"SELECT r.type, e2.name, e2.source_note FROM relationships r JOIN entities e2 ON r.target_id=e2.id WHERE r.source_id IN (SELECT id FROM entities WHERE name LIKE '%{키워드}%') LIMIT 30\\\")]\"")

  3. 커뮤니티 연관 노트:
     엔티티가 속한 커뮤니티의 다른 멤버 조회:
     Bash("python3 -c \"import sqlite3; c=sqlite3.connect('{DB_PATH}').cursor(); [print(r) for r in c.execute(\\\"SELECT DISTINCT e2.name, e2.source_note FROM entities e1 JOIN entities e2 ON e1.community_id=e2.community_id WHERE e1.name LIKE '%{키워드}%' AND e2.name!=e1.name LIMIT 15\\\")]\"")

  > sqlite3 CLI가 미설치된 환경에서도 Python sqlite3 모듈로 동작합니다.

  4. 결과를 graphrag_results에 저장 → Phase C 교차 검증에 포함

ELSE:
  → GraphRAG DB 미존재. Phase A-G 스킵.
  → 안내: "GraphRAG 빌드가 필요합니다. /km Mode G 또는 매일 20:00 자동 빌드를 기다려주세요."
```

> **Phase A-G는 Phase A(wikilink)와 병행 실행 가능.** 둘 다 읽기 전용이므로 충돌 없음.
> 하이브리드 검색이 Dense Embedding(시멘틱) + FTS5(키워드) + Reranker를 자동 결합합니다.
> embedding index 미존재 시 기존 LIKE 검색으로 graceful fallback합니다.

### Phase B: 키워드 검색 (retrieval-specialist 로직)

```
1. 키워드 검색:
   - CLI: `"$OBSIDIAN_CLI" search query="{핵심 키워드}" format=json limit=20` → 파일 목록 반환
   - 컨텍스트 필요 시: MCP `mcp__obsidian__search_vault` 사용 (매칭 라인 컨텍스트 포함)
   - ⚠️ CLI `search:context`는 v1.12.4에서 불안정 (exit 255) → CLI `search` + MCP 컨텍스트로 대체
   - Grep으로 vault 전체 검색 (한국어 + 영어 키워드)
   - 결과 TOP 20 정리

2. 태그 검색:
   - CLI: `"$OBSIDIAN_CLI" tags counts sort=count format=json` → vault 전체 태그 + 빈도
   - CLI: `"$OBSIDIAN_CLI" tags path="{관련폴더}" format=json` → 폴더 한정 태그
   - Grep으로 tags: 또는 #태그 패턴 검색 (폴백)
   - 관련 태그 식별 및 해당 노트 수집

3. 폴더 기반 검색:
   - Library/Zettelkasten/ 하위 관련 폴더 식별
   - Library/Research/ MOC 파일 검색
   - Mine/ 하위 사용자 직접 작성 콘텐츠 검색
```

### Phase C: 교차 검증

```
3-way 교차 검증: Graph(A) ∩ GraphRAG(A-G) ∩ Retrieval(B):

- 3가지 모두 발견 → 최우선 핵심 노트 (강한 확신)
- 2가지에서 발견 → 핵심 노트 (높은 확신) → 우선 처리
- Graph(A)에만 있음 → wikilink 기반 발견 (구조적 연결) → 보조 참조
- GraphRAG(A-G)에만 있음 → 의미적 연관 발견 (엔티티/커뮤니티 기반) → 보조 참조
- Retrieval(B)에만 있음 → 고립 노트 (키워드 매칭, 연결 없음) → 링크 후보

교차 검증 결과 테이블:
| Category | Count | Notes |
|----------|-------|-------|
| Core (양쪽 발견) | N | ... |
| Graph Only | N | ... |
| Retrieval Only | N | ... |
```

---
