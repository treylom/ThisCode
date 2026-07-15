---
title: GraphRAG 운영 Runbook (모델 독립)
order: 7
---

# GraphRAG 운영 Runbook — 어떤 AI 운영자(모델)든 이 문서로 운영 가능

> 설치는 [06-graphrag-setup.md](06-graphrag-setup.md). 본 문서 = 설치 *이후*의
> 일상 운영·코드 변경·장애 대응. 봇의 검색 *사용* 규칙은
> [rules/search-usage.md](../rules/search-usage.md), 도구 *선택*은
> [rules/knowledge-retrieval.md](../rules/knowledge-retrieval.md).
>
> **원칙 1**: 이 문서의 명령은 복사-붙여넣기로 실행 가능해야 한다.
> **원칙 2 (모델 독립 계약)**: 운영자(모델)가 바뀌어도 본 문서 + 설계 기록만으로
> 온보딩이 끝나야 한다. 부족하면 머리로 때우지 말고 **문서를 보강**하는 것이 정답.
> **원칙 3**: 시스템을 바꾸면 *같은 변경에서* 본 문서와 search-usage.md 의
> 기대치를 갱신한다 (stale 지침 = 전 봇 오염).

## 0. 시스템 한 장 요약

vault(md 노트) → **추출기**(wikilink·tag 규칙으로 개념·관계 추출) → **그래프
DB**(SQLite) + **임베딩 인덱스** → **검색 서버**(:8400, hybrid + reranker) →
봇들의 검색 skill/MCP.

| 구성요소 | 기본 경로 | 정상 신호 |
|---|---|---|
| 루트 | `<vault>/.team-os/graphrag/` | — |
| 인덱스 | `index/` (db·npy·entity_meta.json) | db 수백MB대 · meta ~MB대 |
| 가상환경 | `.venv/` | **모든 python 실행은 `.venv/bin/python3`** (시스템 python 은 deps 부재로 *가짜 실패*) |
| 서버 | `http://localhost:8400` | `/health` 200 |

## 1. 스케줄러 (역할 분리가 핵심)

| job | 역할 | 주기 권장 |
|---|---|---|
| server | 검색 서버 상시 | KeepAlive |
| incremental | 증분 갱신 (노트 변경 따라잡기) — dense 재임베딩은 하지 않고 worker 에 요청만 남김 | 30분 (10분 이하 = 서버 블로킹 회귀 이력) |
| embedding-worker | dense 노트 임베딩 전담 (외부 프로세스·CPU) — staging→verify→promote→activate 세대 관리, 서버 GPU 점유 wedge 차단 | 5분 tick (요청 없으면 no-op) |
| rebuild | 풀빌드 (커뮤니티·centrality 재계산) | 새벽 1회 |
| monitor | 외부 헬스 감시 (응답시간 초과 → push 알림) | 주기형 |

> **임베딩 워커 분리 이유** (2026-07 실장): 서버 in-process 재임베딩이 GPU(Metal/MPS)를 점유해 검색 자체를 수백 초 wedge 시키던 회귀의 본수리. `embedding_worker.py`(스크립트 동봉)가 색인을 별도 세대 디렉터리에 빌드→검증→승격하고 서버는 reload 만 받는다. 일일 풀빌드도 `embedding_worker.py`의 staging→verify→promote 경로를 재사용하며, 빌드 후 위생(로그 로테이션·sync_log 정리·stale 파일 보고)은 `graphrag_maintenance.py`.

```bash
# macOS launchd 예 — 상태 / 정지(가역) / 재개
launchctl list | grep graphrag
launchctl bootout gui/$(id -u)/<job-label>
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<job-label>.plist
```
Linux/WSL 은 systemd 타이머로 동형. ▶ Fill in: 실제 job label 4개.

## 2. 일상 점검 (1분)

```bash
curl -s -o /dev/null -w "ready=%{http_code} t=%{time_total}s\n" http://localhost:8400/ready
ls -la index/                                   # db·meta 크기가 §0 정상 신호 밖이면 §4.3
tail -5 <incremental 로그>                       # "Up to date" 또는 added/modified 소수
sqlite3 "file:index/<db>?mode=ro" "SELECT COUNT(*) FROM entities WHERE length(name)>10000;"  # 0 이어야 함
```
▶ Fill in: 정상 시간 기대치 실측값 (예: ready ~2ms · warm 0.2s · cold 1.5s · 재기동 워밍업 ~25s).

## 3. 코드 변경 절차 (순서 고정)

1. `scripts/` 수정 → 2. **전체 테스트** `.venv/bin/python3 -m unittest discover -s scripts -p "test_*.py"` (전건 OK — 시스템 python ❌) → 3. 서버 재시작 → 4. §2 점검 + 실검색 1회 → 5. 벤치 회귀(§5) → 6. 본 문서·search-usage.md 기대치 갱신.

> ⚠️ **3번(서버 재시작)을 건너뛰면 안 되는 이유** (2026-07 실사고): 서버는 `incremental` 등 스크립트 모듈을 기동 시 import 해서 **메모리에 들고 있다**. 파일만 고치고 재시작을 안 하면 CLI 경로는 새 코드, 서버 경로(`POST /api/index/update`)는 옛 코드로 갈라져 — "고쳤는데 안 고쳐진" 상태가 침묵으로 지속된다. 스케줄러 재개보다 서버 재시작이 항상 먼저다.

## 4. 장애 대응 (증상 → 진단 → 처치)

### 4.1 서버 무응답 / OOM kill
- 진단: 스케줄러의 마지막 exit code + 서버 프로세스 RSS (정상 ~수백MB; GB대 = §4.3 의심).
- 처치: 서버 재시작 → 워밍업 대기 → §2 점검.

### 4.2 검색이 자주 fallback 경로로 빠짐
- 진단: 로그에서 "server not ready" 비율. 원인 이력: 증분 갱신이 서버를 블로킹.
- 처치: 변경 0건 시 reload skip + 비동기 갱신 패치 적용 확인, 증분 주기 완화(§1).

### 4.3 🚨 DB·노트 비대 — 자기출력 재소비(escape-배증) 류
- **증상**: db GB대 / meta 수백MB / 어느 노트가 수십MB+ / 서버 RSS 폭증.
- **기전(실사례 2026-06)**: 추출기가 노트 frontmatter 의 *시스템 출력 필드*를
  입력으로 재소비 → escape 가 매 빌드 중첩 → 기하급수 증식. **자동화가 자기
  출력을 다시 먹는 경로는 설계 시점에 차단**이 본질 처방 (코드 가드:
  frontmatter strip + entity name 길이/개행 reject + sync sanitize + 회귀 테스트).
- **처치 절차** (백업 → 정지 → 정화 → 검증, 전 과정 가역):
  ```bash
  # 1) 빌드 정지 + 백업
  launchctl bootout gui/$(id -u)/<rebuild> gui/$(id -u)/<incremental> 2>/dev/null
  mkdir -p ~/quarantine-$(date +%F) && cp index/<db> index/entity_meta.json ~/quarantine-$(date +%F)/
  # 2) 오염 행 특정·삭제 (서버 정지 후)
  sqlite3 index/<db> "SELECT id,length(name) FROM entities WHERE length(name)>10000;"
  #    → 해당 id 를 entities/relationships/FTS 에서 DELETE 후: PRAGMA optimize; VACUUM;
  # 3) 오염 노트는 frontmatter 종결 '\n---\n' 경계를 스트림 스캔해 본문만 추출·복구
  # 4) 서버 재기동 → §2 점검 → 빌드 재개
  ```

### 4.4 인덱스 staleness (새 노트가 검색 안 됨)
- 진단: incremental 로그 최근 실행 시각 + 스케줄러 등재 여부.
- 처치: 등재 없으면 §1 재개. 수동 1회 실행 스크립트로 즉시 따라잡기.

## 5. 벤치마크 (성적 재기)

- 단일 정본 하네스 하나만 유지 (A축 retrieval hit@k/MRR + B축 answer 품질).
- ⚠ **오염 DB 위에서 잰 과거 수치는 비교 기준이 아니다** — 정화·구조 변경 후엔
  반드시 재측정값을 새 baseline 으로.
- 결과는 KEEP/DISCARD 정직 기록으로 누적 (악화 실험도 기록이 자산).

## 6. 운영자(모델) 교체 온보딩

온보딩 입력 = ① 본 문서 ② 설계 기록(왜 이렇게 만들었나 — 채널 가중·LLM 추출
보류 근거·frontmatter 2층 규율·사건 전말) ③ 직전 회의/변경 로그. 이 3개로
부족하면 본 문서를 보강하라.

## 7. codex 환경에서 검색 쓰기 (샌드박스 함정 2개)

codex CLI 세션은 기본 `read-only` 샌드박스가 **로컬호스트 HTTP까지 차단**한다 (curl exit 7).
검색 서버(:8400)에 닿으려면:

```bash
# 1회성 — 명령마다
codex exec --sandbox workspace-write -c sandbox_workspace_write.network_access=true ...
```

```toml
# 영구 — $CODEX_HOME/config.toml (재시작 후 적용; CLI -c 와 1:1 매핑)
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true
```

- ⚠ `read-only` 인 채로 network_access 만 켜면 **무시된다** — 반드시 workspace-write 이상과 짝.
- ⚠ network_access=true 는 외부 네트워크도 열린다 — 신뢰 작업 전용 세션에만 영구 적용, 그 외 1회성 권장.
- 결과 JSON의 문서 식별 필드 = `entity`·`source_note`·`description` (`title` 없음 — null 함정):
  `curl -s "http://127.0.0.1:8400/api/search?q=<질의>&top_k=5" | jq -r '.results[] | "\(.entity)\t\(.source_note)"'`
- 상시 봇에 기본 탑재하려면: 영구 설정 + 행동 규칙 1줄("vault 내용 질문 = 검색 먼저") + 기기 경계 주의(다른 머신 봇은 그 머신의 서버로).

## 8. 관계 재분류 도구 (relabel/)

generic 관계(`related_to`)가 그래프의 다수를 차지하면 `vendor/graphrag/relabel/README-method.md`
파이프라인으로 의미 타입(parent/cites/precedes …)을 재부여할 수 있다 — 파일럿(무작위 표본) → 전량 →
저신뢰 2차 재심 → merge(증분 정지 필수) → 보존 가드 순. 증분 재추출이 의미 라벨을 되돌리지 않는 가드는
`incremental.py`에 이미 내장(§3 재시작 규율과 함께 적용).
