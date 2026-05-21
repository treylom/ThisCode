# knowledge-manager — 결과 보고 / Vault 동기화 / 참조 스킬 / Auto-Learned

> SKILL.md 에서 분리. 보고·동기화·참조는 on-demand.

## 처리 결과 보고

### 입력 요약
- 소스: [URL/파일/vault종합]
- 모드: 단일 에이전트 순차 처리 (Orchestrator Pipeline)

### Vault 탐색 결과
| 카테고리 | 수 | 비고 |
|----------|---|------|
| 핵심 노트 (교차검증) | N | Graph ∩ GraphRAG ∩ Retrieval |
| GraphRAG 연관 | N | 커뮤니티 기반 발견 |
| 관계 기반 발견 | N | Graph only |
| 키워드 매칭 | N | Retrieval only |

### Lint 결과 (STEP 4.5)
- lint_score: {score} / 1.0 (통과 기준: 0.7)
- 반복 횟수: {round}/3
- 주요 수정: [inconsistency N건, missing data N건, connections N건]

### 처리 요약
- 검색된 관련 노트: N개
- 교차 검증 핵심 노트: N개
- 생성된 노트: N개
- 추가된 양방향 링크: N개

### Filed Back (환류)
- 기존 노트 수정: N건
- Open Questions 생성: N건 → {경로}
- 다음 세션 탐색 시드: N개

### 이미지 처리 (image_extraction != false 시)
- 수집 이미지: N개
- 다운로드 성공: N개
- 임베딩 완료: N개
- 저장 경로: Resources/images/{topic-folder}/

### 출력 위치
| 노트 | 경로 | 상태 |
|------|------|------|
| [MOC명] | Research/... | 성공 |
| [Open Questions] | Research/.../Open-Questions-... | 환류 |
| ... | ... | ... |

### 파이프라인 실행 체크 (STEP 스킵 방지)
> ⚠️ 아래 체크리스트에서 미실행 STEP이 있으면 보고 전에 반드시 실행.

- [ ] STEP 2: 콘텐츠 추출 (증분 감지 포함)
- [ ] STEP 3: Vault 탐색 (GraphRAG 포함)
- [ ] STEP 4: COMPILE (draft 생성 + Q&A + 모순 표기)
- [ ] STEP 4.5: LINTING (6가지 규칙 + lint_score)
- [ ] STEP 5: STORE (Cross-phase 검증 + 저장)
- [ ] STEP 5.5: PROPAGATE (기존 노트 업데이트)
- [ ] STEP 6-1: 연결 강화 (양방향 wikilink)
- [ ] STEP 6-2: Filed Back (환류 + Open Questions)
- [ ] STEP 6-4: 엔티티 페이지 제안
- [ ] STEP 6-5: 세션 로그 (_km-log.md append)
- [ ] STEP 7: Vault 동기화
```

### 6-4. 엔티티 페이지 자동 생성 제안

> **Karpathy 패턴: log.md는 시간순, 추가 전용(append-only), grep 파싱 가능.**

```
STEP 6 결과 보고 완료 후, vault의 _km-log.md에 자동 append:

LOG_PATH = "Library/Research/_km-log.md"

# 파일 미존재 시 생성:
IF NOT Glob(vault_path + "/" + LOG_PATH):
  CLI: "$OBSIDIAN_CLI" create path="{LOG_PATH}" content="---
title: Knowledge Manager 세션 로그
type: log
tags: [km, log]
---
# KM Session Log
> 추가 전용. grep 파싱: grep '^## \[' _km-log.md | tail -10
"

# 세션 기록 append:
CLI: "$OBSIDIAN_CLI" append path="{LOG_PATH}" content="
## [{날짜}] {모드} | {소스 제목}
- 소스: {URL 또는 파일명}
- 생성: {N} notes, 업데이트: {N} notes, 링크: {N}
- lint_score: {score}, coverage: {rate}%
- propagation: {N} notes touched
- open_questions: {N}
- filed_back: {N} items
"
```

### 6-5. 세션 로그 자동 기록 (_km-log.md) — 모든 작업 완료 후 마지막

> **Karpathy 패턴: 엔티티별 전용 페이지가 있어야 새 소스마다 정보가 축적된다.**

```
STEP 5.5 Propagation 중 발견된 엔티티 중,
vault에 전용 페이지가 없는 주요 엔티티를 식별:

1. GraphRAG entities에서 centrality 상위 엔티티 추출
2. 각 엔티티에 대해 vault 노트 존재 여부 확인:
   Grep("^title:.*{entity_name}", vault_path) 또는
   CLI: "$OBSIDIAN_CLI" search query="{entity_name}" format=json limit=5

3. 전용 페이지 없는 엔티티 → 생성 제안 목록에 추가:
   "다음 엔티티에 대한 전용 페이지를 만들까요?"
   - {entity_name} (centrality: {score}, 언급 횟수: {count})

4. 사용자 승인 시 엔티티 페이지 생성:
   ---
   title: "{entity_name}"
   type: entity-page
   tags: [{관련 태그}]
   graph_entity: "{entity_id}"
   auto_generated: true
   ---
   # {entity_name}
   ## 개요 (자동 생성 — 관련 노트에서 종합)
   ## 관련 소스 (자동 누적)
   ## 연결
```

---

## STEP 7: Vault 동기화 (WSL→Windows)

**노트 생성/수정 후 반드시 실행.** WSL에서 `/mnt/c/` 경로로 직접 쓰면 Windows Obsidian이 즉시 감지하지 못할 수 있습니다.

```bash
# Obsidian vault 파일 시스템 동기화 (touch로 mtime 갱신)
find "<vault>" -name "*.md" -newer /tmp/.km-sync-marker -exec touch {} + 2>/dev/null

# 또는 rsync로 WSL→Windows 강제 동기화 (생성/수정된 파일만)
rsync -av --update --include="*.md" --exclude="*" \
  "<vault>/Library/" \
  "<vault>/Library/" \
  2>/dev/null || true
```

**간단 버전 (새로 생성한 파일만):**
```bash
# 생성한 노트의 mtime을 강제 갱신 → Obsidian 파일와쳐 트리거
for f in {새로 생성한 파일 경로들}; do
  touch "$f" 2>/dev/null
done
```

> 이 단계 이후 Obsidian에서 노트가 보이지 않으면 `Ctrl+R`(Obsidian 리로드) 안내.

---

## 참조 스킬 (상세 워크플로우)

| 기능 | 참조 스킬 |
|------|----------|
| **Orchestrator Pipeline 오버레이** | `km-karpathy-pipeline.md` |
| 전체 워크플로우 | `km-workflow.md` |
| 콘텐츠 추출 | `km-content-extraction.md` |
| **YouTube 트랜스크립트** | `km-youtube-transcript.md` |
| 소셜 미디어 | `km-social-media.md` |
| 출력 형식 | `km-export-formats.md` |
| 연결 강화 | `km-link-strengthening.md` |
| 연결 감사 | `km-link-audit.md` |
| Obsidian 노트 형식 | `zettelkasten-note.md` |
| 다이어그램 | `drawio-diagram.md` |
| **이미지 파이프라인** | `km-image-pipeline.md` |
| **Mode R: 아카이브 재편** | `km-archive-reorganization.md` |
| **Mode R: 규칙 엔진** | `km-rules-engine.md` |
| **Mode R: 배치 실행** | `km-batch-python.md` |
| **Mode G: GraphRAG 워크플로우** | `km-graphrag-workflow.md` |
| **Mode G: 온톨로지 설계** | `km-graphrag-ontology.md` |
| **Mode G: 그래프 검색** | `km-graphrag-search.md` |
| **Mode G: 인사이트 리포트** | `km-graphrag-report.md` |
| **Mode G: Frontmatter 동기화** | `km-graphrag-sync.md` |

---



## Auto-Learned Patterns

- [2026-04-04] STEP 0에 /using-superpowers 강제 게이트를 삽입해야 스킬 호출 누락을 방지할 수 있다 — 없으면 파이프라인 전체 무효화 위험 (source: 2026-04-04-1732.md)
- [2026-04-05] 증분 모드에서 소스 감지는 URL 매칭만이 아닌 3단계 탐색(URL + 제목 + 폴더)이 필요하다 — 단일 매칭 방식은 근본 결함 (source: 2026-04-05-0349.md)
- [2026-04-05] STEP 6-3 결과 보고에 파이프라인 실행 체크리스트를 포함해야 STEP 스킵을 방지할 수 있다 (source: 2026-04-05-0339.md)
