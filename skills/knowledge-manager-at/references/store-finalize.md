# knowledge-manager-at — STEP 5~6 + 결과 보고 + 참조 스킬

> SKILL.md 에서 분리. 노트 생성/이미지/연결강화/보고는 on-demand.

## STEP 5: 노트 생성 (Main이 직접 실행!)

**CRITICAL**: 노트 생성은 **반드시 Main이 직접** 수행합니다.
팀원에게 쓰기 작업을 위임하면 안 됩니다! (Bug-2025-12-12-2056)

### 5-1. Obsidian 노트 생성

```bash
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

---

## STEP 5.25: 이미지 저장 및 임베딩 (image_extraction_enabled 시 — Main 직접 실행!)

**CRITICAL**: 이 Phase는 `image_extraction_enabled = true`일 때만 실행합니다.
**CRITICAL**: 파일 저장은 반드시 Main이 직접 수행! (Task 에이전트 쓰기 버그 방지)

참조 스킬: `km-image-pipeline.md`

### Phase 5.25 워크플로우

```
1. content-extractor Image Catalog 파싱:
   - content-proc-lead 보고서에서 Image Catalog 테이블 추출
   - 각 이미지의 Type, Source, URL/Path, Context, Placement 확인

2. Resources/images/{topic-folder}/ 디렉토리 생성:
   Bash("mkdir -p <vault>/AI_Second_Brain/Resources/images/{topic-folder}/")

3. 각 이미지 다운로드/복사:

   웹 이미지:
   Bash("curl -sLo '<vault>/AI_Second_Brain/Resources/images/{topic-folder}/{NN}-{descriptive-name}.{ext}' '{url}'")

   PDF 이미지 (marker 출력):
   Bash("cp km-temp/{name}/images/{file} '<vault>/AI_Second_Brain/Resources/images/{topic-folder}/{NN}-{descriptive-name}.{ext}'")

4. 다운로드 실패 시 Playwright 스크린샷 폴백:
   - 원본 URL로 navigate
   - browser_take_screenshot으로 해당 요소 캡처
   - 저장 경로: Resources/images/{topic-folder}/{NN}-screenshot.png

5. 노트 콘텐츠에 이미지 임베드 (본문 흐름 배치!):
   - 개념 설명 → (빈 줄) → ![[Resources/images/{topic-folder}/{filename}]] → (빈 줄) → 상세 설명
   - content-analyzer의 Placement 제안에 따라 적절한 위치에 삽입
   - 이미지 연속 배치 금지 (반드시 텍스트로 분리)

6. Notion 페이로드에 이미지 블록 추가:
   - 외부 URL 이미지: { "type": "image", "image": { "type": "external", "external": { "url": "{원본URL}" } } }
   - 로컬 전용 이미지: callout 블록으로 대체 — "[이미지: Resources/images/{topic-folder}/{filename}]"

7. 저장 검증:
   Glob("AI_Second_Brain/Resources/images/{topic-folder}/*") → 파일 존재 확인
   각 이미지 파일 크기 > 0 확인
```

### 대시보드 진행률 (Phase 5.25)

```
IF dashboard_available AND image_extraction_enabled:
  Bash("curl -s -X POST http://localhost:3747/api/progress -H 'Content-Type: application/json' -d '{\"agent\":\"Lead\",\"progress\":72,\"task\":\"이미지 저장 중\",\"note\":\"Phase 5.25\"}' --connect-timeout 2 || true")
```

---

## STEP 6: 연결 강화 + 팀 정리

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

### 6-2. 팀 셧다운 + 활동 로그 (tofu-at STEP 7-7 패턴)

```
PRECONDITION (셧다운 전제 조건 — DA 활성화):
  da_review.recommendation == "ACCEPTABLE"
  OR da_iteration >= 3

# DA 미승인 시 셧다운 불가 — STEP 4 Phase 3 완료 후에만 진행

0. 전 agent Progress → 95% curl push (셧다운 직전):
   FOR each agent in [Lead, vault-intel-lead, content-proc-lead, graph-navigator, retrieval-specialist, link-curator, content-extractor, deep-reader, content-analyzer, devils-advocate]:
     TEAM_PROGRESS.md: Progress → 95%, Note → shutting down
     IF dashboard_available:
       Bash("curl -s -X POST http://localhost:3747/api/progress -H 'Content-Type: application/json' -d '{\"agent\":\"{agent}\",\"progress\":95,\"task\":\"shutdown\",\"note\":\"shutting down\"}' --connect-timeout 2 || true")

1. 각 팀원에게 shutdown_request:
   FOR each member in [vault-intel-lead, content-proc-lead, graph-navigator, retrieval-specialist, content-extractor, deep-reader, content-analyzer, link-curator, devils-advocate]:
     SendMessage({ type: "shutdown_request", recipient: "{member}", content: "작업 완료." })

2. shutdown_response 대기 (최대 10초):
   각 팀원의 shutdown_response를 대기.
   10초 내 응답 없는 팀원은 아래 3번에서 강제 정리.

3. 잔류 tmux pane 강제 정리 (CRITICAL — scurrying 방지):
   Read("~/.claude/teams/km-at-{주제키워드}/config.json")
   FOR each member in team_config.members (리드 제외):
     IF member.tmuxPaneId:
       Bash("tmux kill-pane -t {member.tmuxPaneId} 2>/dev/null || true")
   FOR each member in team_config.members (리드 제외):
     IF member.isActive != false:
       config.json에서 해당 member의 isActive = false 설정

4. TeamDelete()

4.1. Results 보고서 자동 전송 (MANDATORY — TeamDelete 직후):
   report = {
     "id": "{timestamp}-km-at-{주제키워드}",
     "timestamp": "{ISO 8601}",
     "teamName": "km-at-{주제키워드}",
     "subject": "{주제}",
     "complexity": "AT Full-Scale",
     "duration": "{실행 소요 시간}",
     "sourceCommand": "/knowledge-manager-at",
     "team": [각 role의 { name, role, model, status }],
     "steps": [각 step의 { id, step, assignee, status }],
     "checkpoints": [각 checkpoint의 { name, done }],
     "bulletin": [{최근 bulletin 항목들}],
     "results": { "summary": "...", "details": "...", "artifacts": [...] },
     "ralph": { "iterations": {...}, "verdict": "..." },
     "da": { "recommendation": "...", "iterations": N }
   }

   # Primary: Agent Office 서버로 POST
   IF dashboard_available:
     Bash("curl -s -X POST http://localhost:3747/api/reports -H 'Content-Type: application/json' -d '{report JSON}' --connect-timeout 5")

     # Fallback: curl 실패 시 파일로 직접 저장
     IF curl 실패 (exit code != 0 또는 HTTP != 200/201):
       Bash("mkdir -p .team-os/reports")
       Write(".team-os/reports/{report.id}.json", JSON.stringify(report, null, 2))

5. 대시보드 아티팩트 정리:
   IF dashboard_available:
     Bash("curl -s -X POST http://localhost:3747/api/session/clear --connect-timeout 2 || true")
   → .team-os/artifacts/TEAM_*.md 삭제 (MEMORY.md 유지)
   → 대시보드가 stale 팀 데이터 표시하지 않도록 방지

6. TEAM_FINDINGS.md → MEMORY.md 이관:
   Read(".team-os/artifacts/TEAM_FINDINGS.md")
   → Key Insights → MEMORY.md Lessons Learned 테이블에 추가
   → 주요 결정사항 → MEMORY.md Decisions 테이블에 추가
   → Session Log 테이블에 현재 세션 기록 추가:
     | # | 날짜 | 주제 | 팀규모 | 생성노트 | 연결수 | RALPH횟수 | DA판정 |
```

### 6-3. 결과 보고

```
## 처리 결과 보고

### 입력 요약
- 소스: [URL/파일/vault종합]
- 모드: Agent Teams (풀스케일, 9명)
- Team OS: 활성
- Agent Office: [실행 중 / 미실행]
- Dashboard Push: [활성 / 비활성]

### Agent Teams 요약
| 계층 | 팀원 | 역할 | 모델 | 결과 |
|------|------|------|------|------|
| Cat.Lead | vault-intel-lead | Vault 탐색 조율 | Sonnet 1M | 핵심 {N}개, 관계 {N}개 |
| Cat.Lead | content-proc-lead | 콘텐츠 처리 조율 | Sonnet 1M | 추출 완료, 구조 설계 |
| Worker | @graph-navigator | 그래프 탐색 | Sonnet 1M | Hub {N}개, 1-hop {N}개 |
| Worker | @retrieval-specialist | 키워드 검색 | Sonnet 1M | 관련 노트 {N}개 |
| Worker | @content-extractor | 콘텐츠 추출 | Sonnet 1M | {N} words |
| Worker | @deep-reader | 깊이 읽기 | Sonnet 1M | 교차 분석 {N}개 |
| Worker | @content-analyzer | 구조 설계 | Sonnet 1M | 노트 {N}개 제안 |
| Worker | @link-curator | 링크 추천 | Haiku | 연결 후보 {N}개 |
| DA | @devils-advocate | 반론 검증 | Sonnet 1M | {반론수} 반론, {수용수} 수용 |

### RALPH Loop 요약
| 이터레이션 | 대상 | 피드백 | 결과 |
|-----------|------|--------|------|
| 1 | ... | ... | accepted/retry |

### 처리 요약
- 검색된 관련 노트: N개
- 교차 검증 핵심 노트: N개
- 생성된 노트: N개
- 추가된 양방향 링크: N개
- 이미지 추출 (활성 시): N개 다운로드, N개 임베딩
- 이미지 실패 (있으면): N개 (사유 포함)

### 출력 위치
| 노트 | 경로 | 상태 |
|------|------|------|
| [MOC명] | Research/... | 성공 |

### Checkpoints 요약
| # | Checkpoint | 상태 |
|---|-----------|------|
| 1 | All workers spawned | ✅/❌ |
| 2 | All workers completed | ✅/❌ |
| 3 | Artifacts generated | ✅/❌ |

### DA 종합 리뷰
- Recommendation: {ACCEPTABLE/CONCERN}
- Iterations: {N}
- Rework 대상: {목록 또는 없음}

### Team OS 아티팩트
- TEAM_BULLETIN: .team-os/artifacts/TEAM_BULLETIN.md
- MEMORY: .team-os/artifacts/MEMORY.md
- Findings: .team-os/artifacts/TEAM_FINDINGS.md
- Results: .team-os/reports/{report-id}.json (Agent Office 전송 실패 시)
```

---

## 참조 스킬 (상세 워크플로우)

| 기능 | 참조 스킬 |
|------|----------|
| 전체 워크플로우 | `km-workflow.md` |
| 환경 감지 | `km-environment-detection.md` |
| 콘텐츠 추출 | `km-content-extraction.md` |
| **YouTube 트랜스크립트** | `km-youtube-transcript.md` |
| 소셜 미디어 | `km-social-media.md` |
| 출력 형식 | `km-export-formats.md` |
| 연결 강화 | `km-link-strengthening.md` |
| 연결 감사 | `km-link-audit.md` |
| Obsidian 노트 형식 | `zettelkasten-note.md` |
| 다이어그램 | `drawio-diagram.md` |
| **Mode R: 아카이브 재편** | `km-archive-reorganization.md` |
| **Mode R: 규칙 엔진** | `km-rules-engine.md` |
| **Mode R: 배치 실행** | `km-batch-python.md` |
| **Mode G: GraphRAG 워크플로우** | `km-graphrag-workflow.md` |
| **Mode G: 온톨로지 설계** | `km-graphrag-ontology.md` |
| **Mode G: 그래프 검색** | `km-graphrag-search.md` |
| **Mode G: 인사이트 리포트** | `km-graphrag-report.md` |
| **Mode G: Frontmatter 동기화** | `km-graphrag-sync.md` |

---
