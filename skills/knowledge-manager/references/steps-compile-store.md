# knowledge-manager — STEP 4~5.5 상세 (COMPILE / LINTING / STORE / PROPAGATE)

> SKILL.md 에서 분리(Skills 2.0 ≤500, progressive disclosure). 본 STEP 실행 시 본 파일을 Read 해 그대로 수행.

## STEP 4: COMPILE — raw→wiki 컴파일 (draft 생성)

> **Orchestrator 핵심: "raw → wiki는 컴파일이다."**
> 이 단계의 출력은 **draft** — 아직 확정이 아니다.
> draft는 STEP 4.5 Linting을 통과해야만 STEP 5에서 저장된다.

### 4-1. 콘텐츠 분석 (Compile Phase 1)

```
추출된 콘텐츠 (STEP 2) + vault 탐색 결과 (STEP 3)를 종합하여:

1. 핵심 개념 추출 및 분류
2. 사용자 선호도 반영한 깊이/초점 조정
3. 기존 vault 노트와의 관계 분석
4. [NEW] 모순 즉시 표기 (Orchestrator Ingest 패턴):
   - STEP 3 교차검증 Core 노트의 핵심 주장 추출
   - 새 소스의 주장과 비교
   - 모순 발견 시 draft에 인라인 표기:
     "⚠️ 모순: 기존 [[노트명]]에서는 ~라고 했으나, 이 소스에서는 ~"
   - lint 단계를 기다리지 않고 컴파일 시점에 바로 표기
   - 참고: 이미 표기된 모순은 STEP 4.5 lint 규칙 1에서 중복 탐지하지 않음 (dedupe)
```

### 4-2. 노트 구조 설계 (Compile Phase 2)

```
사용자 선택에 따라:

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

### 4-5. Draft 노트 생성 (Compile Phase 3)

```
위 분석 결과를 바탕으로 draft Wiki 노트를 메모리에 생성.
(아직 Vault에 저장하지 않는다 — STEP 5에서 lint 통과 후 저장)

draft 생성 시 포함:
- YAML frontmatter (tags, author, date, source)
- 본문 (Markdown, wikilink 포함)
- Mine/ vs Library/ 경로 결정 (5-0 라우팅 규칙 사전 적용)

[증분 모드 시 필수] "## 변경점 요약" 섹션:
  이 섹션이 없으면 draft는 lint 불통과. 반드시 포함해야 한다.
  ---
  ## 변경점 요약 (vs 기존 노트)
  ### 추가된 내용 [NEW]
  - {섹션/내용}: {요약}
  ### 수정된 내용 [CHANGED]
  - {섹션}: {기존} → {변경}
  ### 삭제된 내용 [REMOVED]
  - {섹션}: (삭제됨)
  ### 구조 변경 [RENAMED/REORDERED]
  - {변경 사항}
  ---
```

### 4-6. Q&A 양방향 보강

```
컴파일된 draft에서 추가 질문을 도출하여 품질을 높인다:

1. draft에서 "아직 답하지 못한 질문" 3개 도출
   - 본문에서 언급되었으나 설명이 부족한 개념
   - 관련 주제인데 draft가 다루지 않은 영역
   - 기존 vault 노트와 연결 가능하지만 근거가 불충분한 주장

2. STEP 3 enriched_context에서 답변 탐색
   - 교차 검증 Core 노트에서 답변 검색
   - GraphRAG 커뮤니티 관련 노트에서 보강 정보 확인

3. 답변 발견 시 → draft에 반영 (본문 보강)
   답변 미발견 시 → draft에 "## Open Questions" 섹션 추가
   - Open Questions는 다음 KM 세션의 탐색 시드가 된다
```

---

## STEP 4.5: LINTING — 지식 Health Check

> **⚠️ Orchestrator 핵심: "지식에도 Linting이 필요하다."**
> draft 노트의 품질을 검증하고 자동 수정하는 health check 루프.
> **lint 통과 전까지 STEP 5 저장 진행 금지.**
> 참조 스킬: Orchestrator Pipeline 오버레이 (vault-internal — 번들 미포함, 없으면 본 단계 기본 흐름대로)

### 4.5-1. Lint 규칙 6가지

```
1. Find inconsistencies (모순 탐지)
   - draft 노트 vs 기존 vault 노트 간 모순/불일치
   - 같은 개념에 대한 상충 설명, 날짜 오류, 사실관계 충돌
   - STEP 3 교차검증 Core 노트와 비교

2. Impute missing data (누락 보완)
   - frontmatter 누락 필드 (tags, author, date, source)
   - 본문에서 언급되었으나 정의되지 않은 용어
   - wikilink 대상이 vault에 존재하지 않는 경우 → forward ref 표시

3. Suggest new articles (신규 노트 제안)
   - draft가 다루지 않은 관련 주제 식별
   - "이 노트가 있으면 vault 그래프가 더 촘촘해질 것" 후보
   - Open Questions에서 파생 가능한 독립 노트 주제

4. Find connections (숨겨진 연결 발견)
   - draft와 기존 vault 노트 사이의 숨겨진 연결
   - 태그 공유, 개념 유사, 동일 GraphRAG 커뮤니티 소속
   - STEP 3 교차검증에서 "Retrieval Only"였던 고립 노트와의 연결 시도

5. Source coverage check (원문 커버리지 검증) ← LKB self-improve 패턴
   [신규 모드] 원문 키포인트 → draft 커버리지 매핑 → MISSING 보충
   [증분 모드] 원문 변경점 → 기존 노트 반영 여부 검증 → 미반영 항목 표기
   - 증분 시 "## 변경점 요약" 섹션이 draft에 없으면 → lint 실패 (HARD GATE)

6. Orphan detection (고아 페이지 탐지) ← Orchestrator Lint 패턴
   - CLI: "$OBSIDIAN_CLI" orphans → 들어오는 링크(inbound) 없는 페이지 목록
   - CLI: "$OBSIDIAN_CLI" deadends → 나가는 링크(outbound) 없는 페이지 목록
   - 고아 페이지 중 draft와 관련된 것 → wikilink 연결 제안
   - 장기 고아 (30일+ 미연결) → 삭제 또는 통합 제안
   - STEP 2에서 추출한 원문의 주요 섹션/키포인트 목록 생성
   - draft의 각 섹션이 원문 키포인트를 커버하는지 매핑
   - 커버리지 매트릭스: 원문 섹션 × COVERED/MISSING
   - 미커버 포인트 → lint 이슈로 등록 → draft에 보충 또는 Open Questions로 이동
   - "원문에서 이 부분을 빠뜨렸습니다: {섹션명}" 피드백
   - 웹 소스 시: 빠뜨린 부분에 대해 WebSearch로 보충 정보 자동 탐색 (선택적)
```

### 4.5-2. lint_score 채점 (km-tools 자동 계산)

```
LLM이 3개 지표를 0.0-1.0으로 평가한 후 km-tools로 실제 계산:

Bash("python3 agent-office/km-tools/km-tools.py lint {draft_path} --consistency {X} --suggestions {Y} --coverage {Z}")

→ completeness (frontmatter 5필드) + connections (wikilink 수)는 Python이 자동 계산
→ consistency, suggestions, coverage는 LLM이 인자로 전달
→ 가중 합산: consistency×0.25 + completeness×0.20 + connections×0.20 + suggestions×0.15 + coverage×0.20
→ passed=true (≥ 0.7) 시 STEP 5 진행
→ passed=false 시 수정 후 재실행 (최대 3회)
→ LLM 인자 누락 시 해당 지표 0.0 + warnings 배열에 경고
```

### 4.5-3. Lint 반복 루프 (/autoresearch 패턴)

```
baseline = lint_score(draft)   # 초기 측정

FOR round IN 1..3:             # 최대 3회 반복 (무한루프 방지)
  IF lint_score ≥ 0.7:
    → PASS. "Lint 통과 (score={lint_score}, round={round})"
    → STEP 5로 진행
    → BREAK

  # 6가지 규칙 실행 → 문제 목록 생성
  issues = run_lint_rules(draft)

  # draft 수정 (가장 심각한 이슈부터)
  draft = fix_issues(draft, issues)

  # 재측정
  new_score = lint_score(draft)

  # /autoresearch 판정: 개선 시 keep, 악화 시 discard
  IF new_score > prev_score:
    → keep: "Lint R{round}: {prev_score} → {new_score} (+{delta})"
    prev_score = new_score
  ELSE:
    → discard: 수정 롤백, 다른 접근 시도 (keep/discard 단순 판정)
    draft = rollback(draft)

IF lint_score < 0.7 after 3 rounds:
  → lint_status = "WARN" (미통과이나 lint는 실행됨)
  → "Lint 미통과 (score={lint_score}). 최선 draft로 진행합니다."
  → STEP 5 진행 가능 (lint를 실행했으므로 게이트 통과)
  → 단, 보고서에 lint 미통과 사유 + 잔여 이슈 목록 필수 포함
```

---

## STEP 5: STORE — 노트 저장 (lint 통과된 draft만!)

**CRITICAL**: 노트 생성은 **반드시 Main이 직접** 수행합니다.
**CRITICAL**: **STEP 4.5 lint를 실행한 draft만 저장한다.** lint 미실행(스킵) 시 이 단계 진입 금지.
> lint_status가 "PASS" 또는 "WARN"이면 진행 가능. lint 자체를 실행하지 않은 경우만 차단.

### 5-PRE. Cross-phase 검증 (저장 직전 최종 확인)

```
저장 전 3가지 Cross-phase 검증 수행:

1. 제목 중복 체크:
   Grep("^# {draft_title}", vault_path) 또는
   CLI: "$OBSIDIAN_CLI" search query="{draft_title}" → 동일 제목 노트 존재 여부
   → 중복 시: 기존 노트에 append 또는 제목 변경 제안

2. 태그 일관성 체크:
   draft의 tags vs STEP 4.5에서 확정된 tags 비교
   → 불일치 시: lint 확정 태그로 교정

3. 이미지:임베딩 비율 체크 (image_extraction != false 시):
   수집된 이미지 수 vs 본문 ![[]] 임베딩 수
   → 불일치 시: 누락 임베딩 추가 또는 미사용 이미지 제거
```

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
- Vault root = `AI_Second_Brain`
- 경로는 vault root 기준 상대 경로
- `AI_Second_Brain/`를 prefix로 붙이지 말 것!

### 5-0. 저장 경로 결정 (CRITICAL — 모든 노트 생성 전 필수!)

**Mine/ vs Library/ 라우팅**: 노트 생성 전 반드시 아래 규칙으로 경로를 결정합니다.

```
Q: "이 콘텐츠의 원저자가 vault 주인(owner)인가?"

YES → Mine/ 하위:
  - 얼룩소 원문           → Mine/얼룩소/
  - 본인 Threads/SNS 원문 → Mine/Threads/
  - 참고 자료             → Resources/
  - 에세이/분석/에버그린  → Mine/Essays/
  - 업무 산출물 (CV 등)   → Mine/Projects/

NO → Library/ 하위 (기본):
  - YouTube/웹 정리       → Library/Zettelkasten/{적절한 주제폴더}/
  - 대규모 리서치 (3-tier) → Library/Research/{프로젝트명}/
  - 외부 Threads          → Library/Threads/
  - 학술 논문             → Library/Papers/
  - 웹 클리핑/가이드      → Library/Clippings/
  - 기타 외부 리소스      → Library/Resources/
```

**판별 시그널 (우선순위)**:
1. author 필드 = vault 주인 핸들(사용자 CLAUDE.md 에 선언) → Mine/
2. source URL에 본인 핸들 포함 → Mine/Threads/
3. tags에 본인 핸들 포함 → Mine/
4. 위 해당 없음 → Library/

### 5-0-PLUS. 기존 상위 MOC parent 자동 등록 (2026-04-21 운영 규율)

> **"하나의 문서, 복수 MOC 소속."** Phase A0 `candidate_parent_mocs` 중
> 작성자·주제와 일치하는 MOC를 새 노트 frontmatter `parent` 필드에 복수 등록.

```
IF len(candidate_parent_mocs) > 0:
  matched_mocs = [moc for moc in candidate_parent_mocs if moc.score >= 3]
  # 기준: 작성자 일치(+3) 또는 태그 2개+ 일치

  IF len(matched_mocs) > 0:
    # 최대 3개까지 복수 소속 허용
    new_note.frontmatter.parent = [
      f'"[[{moc.name}]]"' for moc in matched_mocs[:3]
    ]
    # YAML 다중값 예시:
    # parent:
    #   - "[[기초부터-시작하는-AI생활-specal1849-MOC]]"
    #   - "[[specal1849-전체-MOC]]"
  ELSE:
    # 딱 맞는 상위 MOC 없음 → STEP 4.5 lint 규칙 3 "Suggest new articles"
    # 에서 "작성자/주제 허브 MOC 신설" 자동 제안
    lint_suggestions.append({
      "type": "new_hub_moc",
      "reason": "저자·주제 일치 상위 MOC 부재 — 신설 고려"
    })
```

**실제 적용 근거**: 2026-04-21 specal1849 임베딩편 저장 시 이 규율로 parent 2개(카테고리 + 작성자 허브) 소속 구조 완성.

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
1. Resources/images/{topic-folder}/ 디렉토리 생성:
   Bash("mkdir -p <vault>/AI_Second_Brain/Resources/images/{topic-folder}/")

2. 수집된 이미지 다운로드:
   웹 이미지: Bash("curl -sLo '{경로}' '{url}'")
   PDF 이미지: Bash("cp km-temp/{name}/images/{file} '{경로}'")
   실패 시: Playwright 스크린샷 폴백

3. 노트 콘텐츠에 이미지 임베드 삽입 (본문 흐름 배치!):
   - 개념 설명 → (빈 줄) → ![[Resources/images/{topic-folder}/{filename}]] → (빈 줄) → 상세 설명
   - 이미지 연속 배치 금지 (반드시 텍스트로 분리)

4. 검증:
   Glob("AI_Second_Brain/Resources/images/{topic-folder}/*") → 파일 존재 확인
```

**auto 모드 제한**: 차트/다이어그램만, 최대 10개, > 2MB 이미지 스킵

---

## STEP 5.5: PROPAGATE — 기존 노트 업데이트 (Orchestrator Wiki Pattern)

> **Orchestrator 핵심: "단일 소스가 10-15개 기존 위키 페이지를 터치한다."**
> 새 노트를 생성하는 것만으로는 지식이 복리로 쌓이지 않는다.
> 기존 노트에 새 정보를 반영해야 위키가 compounding artifact가 된다.

### 5.5-0. 상위 MOC 역링크 자동 추가 (2026-04-21 운영 규율)

> 새 노트가 `parent` 필드로 등록한 상위 MOC에 역방향 wikilink 등록. 중복 방지.

```
FOR EACH parent_moc IN new_note.frontmatter.parent:
  1. parent_moc 파일 Read
  2. 적절한 섹션 탐색 (우선순위):
     - "## 📚 시리즈 구성" 또는 "## 📖 원자 노트"
     - "## 🗺️ 시리즈 MOC" (작성자 허브 MOC용)
     - "## 관련 노트"
     - 섹션 미발견 시: 파일 끝에 "## 📎 자동 등록 노트" 섹션 신설
  3. 중복 체크: 기존 내용에 `[[{new_note_name}]]` 존재 여부 → 있으면 skip
  4. append:
     - 시리즈/카테고리 MOC: "- [[{new_note_name}]] — {한 줄 설명}"
     - 작성자 허브 MOC: "- {한 줄 설명} — [[{new_note_name}]]"
  5. parent_moc frontmatter `graph_connections`에
     `"{new_note_name} (contains)"` 추가 (기존 리스트에 append)
```

**실제 적용 근거**: 2026-04-21 specal1849 허브 구축 시 이 규율로 6개 MOC에 parent 역링크 전파. 수동 수행을 자동화로 승격.

### 5.5-1. 핵심 엔티티/개념 추출

```
새로 저장된 draft에서 핵심 엔티티와 개념을 추출:

1. frontmatter tags에서 주요 키워드 추출
2. 본문 heading(##)에서 주제어 추출
3. wikilink 대상 노트 목록 수집
4. GraphRAG entities 테이블에서 관련 엔티티 조회 (DB 존재 시):
   Bash("python3 -c \"import sqlite3, os; db=os.environ.get('DB_PATH') or os.popen('git rev-parse --show-toplevel 2>/dev/null').read().strip()+'/.team-os/graphrag/index/vault_graph.db'; c=sqlite3.connect(db).cursor(); [print(r) for r in c.execute(\\\"SELECT name, source_note FROM entities WHERE name LIKE '%{키워드}%' LIMIT 20\\\")]\"")
```

### 5.5-2. 기존 노트 업데이트 대상 식별

```
추출된 엔티티/개념으로 업데이트 대상 노트 탐색:

1. wikilink 역추적:
   Grep("\\[\\[{draft_title}\\]\\]", vault_path) → 이미 이 노트를 참조하는 기존 노트

2. 동일 태그 노트:
   CLI: "$OBSIDIAN_CLI" tags path="{관련폴더}" → 동일 태그를 가진 노트

3. GraphRAG 커뮤니티 소속 노트:
   같은 community_id를 가진 다른 엔티티의 source_note

4. MOC/인덱스 노트:
   해당 주제의 MOC에 새 노트가 아직 등록되지 않았으면 등록 대상

→ 업데이트 대상 목록 (최대 15개, 관련도순 정렬)
```

### 5.5-3. 업데이트 실행

```
FOR EACH target_note IN update_targets (최대 15개):

  1. target_note Read → 현재 내용 확인

  2. 업데이트 유형 판별:
     a) MOC/인덱스 → 새 노트 항목 추가 (append)
     b) 엔티티/개념 페이지 → "## 최근 업데이트" 또는 관련 섹션에 새 정보 추가
     c) 관련 주제 노트 → "## 관련 노트" 섹션에 wikilink 추가
     d) 모순 발견 → "⚠️ 모순" 인라인 표기 + 태그 추가

  3. 업데이트 실행:
     CLI: "$OBSIDIAN_CLI" append path="{target_path}" content="{추가 내용}"
     또는 MCP: mcp__obsidian__update_note (surgical edit 필요 시)
     또는 Write (폴백)

  4. 변경 기록:
     propagation_log에 추가: {target_note, update_type, content_added}
```

### 5.5-4. Propagation 보고

```
## Propagation 결과
- 업데이트 대상 식별: N개
- 실제 업데이트: N개
  - MOC/인덱스 등록: N건
  - 정보 추가: N건
  - wikilink 추가: N건
  - 모순 표기: N건
- 스킵 (변경 불필요): N건
```

---
