# GraphRAG 관계 재분류 (relabel) — 방법론·이식 가이드

지식그래프의 generic 관계(`related_to`)에 노트 본문 근거로 의미 타입(parent/cites/precedes 등)을 다시 붙이는 파이프라인.
LLM 호출은 codex CLI 키리스(`codex exec --ephemeral`) — API 키·비용 0.

## 전제

- GraphRAG 인덱스(`vault_graph.db`)와 라이브 Obsidian vault
- `codex` CLI 로그인 상태 (기본 모델 gpt-5.5, 2차 패스는 reasoning 모델 권장)
- **머지 단계에서만** 증분 색인 정지 필요 (판정 단계는 DB read-only)

## 실행 순서

```bash
export T1_DB=/path/to/index/vault_graph.db
export T1_VAULT=/path/to/YourVault

# 0) 스모크 (10쌍) → 1) 파일럿: 무작위 100쌍 = 모집단 전환율 추정 (degree 상위는 과대추정)
python3 pilot_runner.py 10 random
python3 pilot_runner.py 100 random

# 2) 본run: 전량 (degree 내림차순 = 고가치 쌍 선판정, resume 내장 — 끊겨도 재실행이 이어받음)
python3 pilot_runner.py 999999 full 8      # nohup 권장, 규모 = related_to 수 × ~2s/쌍 ÷ 워커수 (실측 22,794쌍·8워커 ≈ 112분)

# 3) 2차 패스: 저신뢰(conf<0.8) 전환분만 reasoning 모델 재심 (하이브리드 — 억지 라벨 차단)
#    대상 rid 추출 후:
T1_MODEL=gpt-5.6-luna T1_EFFORT=xhigh T1_TIMEOUT=300 T1_RIDS_FILE=$PWD/pass2-rids.txt \
  python3 pilot_runner.py 999999 rids 8

# 4) merge: 증분 색인 정지 확인 후! (backup API 스냅샷 → 이중가드 UPDATE → 전후 카운트 assert)
python3 merge_apply.py
```

## merge 적용 규칙 (원자료 보존 — JSONL은 불변, 필터는 merge 층)

- pass2 override: ①동일 타입 → 유지 ②다른 의미 타입 → reasoning 모델 채택 ③related_to 판정 → 전환 취소
- 최종 confidence < 0.7 → related_to 보류 (`T1_CONF_CUT`)

## 재발 방지 가드 (필수 — 없으면 증분 색인이 라벨을 되돌림)

증분 스크립트(incremental.py)의 **modified 노트 재추출 DELETE**를 generic 한정으로:

```sql
DELETE FROM relationships WHERE source_note = ? AND type IN ('related_to','mentions')
```

- ⚠️ **deleted 노트 정리 DELETE에는 걸지 말 것** (노트가 사라진 경우 전삭이 정답 — 가드 시 orphan 잔존)
- ⚠️ **검색 서버가 incremental 모듈을 import 하는 구조면 서버 재시작 필수** — 장수 프로세스는 가드 이전 모듈을 메모리에 들고 있어, 재시작 없이 증분 재개 시 가드 무효

## 회귀 테스트 2케이스 (가드 배선 후, 증분 재개 전)

1. modified: 의미 라벨 보유 노트의 `note_graph_state.content_hash` 무효화 → 증분 1틱 → 의미 라벨 잔존 + 전역 의미 총계 불변
2. deleted: 임시 노트 생성→추출 확인→삭제→증분 1틱 → 그 관계 전삭(orphan 0)

## 실측 참고치 (13K 노트·22,794쌍 vault, 2026-07-15)

| 항목 | 값 |
|---|---|
| 본run | 112분 (8워커, ~10s/콜·배치5) · 실패 0 |
| 전환율 | 무작위 29% · degree 상위 98.8% (MOC-heavy) · 최종 24.8% (2차 패스 후) |
| 2차 패스 | 저신뢰 2,510건 중 57% 환원 (근거 박약 차단) |
| 비용 | 0원 (codex 키리스) |

## 타당성 위협

판정은 링크 주변 발췌(650자) 기준 — 문맥 밖 근거 미반영. 단일 판정(투표 없음), 저신뢰 구간만 2차 재심으로 보강. 시리즈 연번처럼 "제목 자명" 관계는 발췌 근거 부족으로 환원될 수 있음(결정적 후처리 룰로 복원 가능).
