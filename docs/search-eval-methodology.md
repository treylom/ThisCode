# GraphRAG / 검색 품질 평가 방법론 (search-eval)

> 배포 번들(ThisCode/ThisCodex) 동봉용 일반화 패턴. vault GraphRAG `/search`를 "잘 된다/안 된다" 감으로 단정하지 말고 **수치로 측정·개선**하는 재사용 방법론. (출처 사례: obsidian-ai-vault 2026-06-06 search-enhancement 회의.)

## 0. 원칙
- **측정 없는 보강 금지.** "검색 잘 됨"은 벤치로 증명. 개선 주장 = before/after 수치 동반(verification-before-completion).
- **라이브 비파괴.** 실험은 격리(별도 포트·복제 코드·branch). "좋아졌다"가 수치로 증명되면만 promote.
- **있는 자산 먼저 audit.** 새 하네스 만들기 전 기존 benchmark/autoresearch 확인(코드=ground truth).

## 1. 쿼리셋 설계
- **레벨 분류(L0~L3)**: L0 직접조회 / L1 관계 / L2 다홉 / L3 코퍼스 합성. 레벨별 강·약을 분리해 봐야 보강 타깃이 보인다.
- **내용 질의(no-memory)**: vault 지식 내용만. 메모리·회의·ops 결정 질의 ❌(평가가 운영 메타에 오염).
- **gold_notes = filesystem 실재 확인**(phantom 금지). 매칭은 **exact basename**(NFKC·`.md` strip·casefold equality) — substring은 zet-version 동명 오매칭.
- 실패 사례를 일부러 포함(예: 흔한 용어의 ranking-burial, frontmatter-only·교차언어 recall).

## 2. 두 축 측정
- **A축 — retrieval(모델 독립)**: 쿼리→검색 서버→top-k에 gold 포함? `hit@5`(상위5에 gold 1개+), `precision@5`, `MRR`(첫 gold 역순위), `coverage`. 서버에 직접 질의, runs≥3.
- **B축 — answer(모델 의존, cross-model)**: 같은 쿼리를 **여러 모델 티어(haiku/sonnet/opus)**가 각자 검색해 답(**cold = 사전지식·메모리 금지, 검색 결과로만**) → judge가 `answer_score·accuracy·grounding·hallucination·refusal(검색 안 함)` 비교 채점.
- 도구: 격리 서버 + benchmark_runner(A축) + cross-model 오케스트레이션(B축, 예 Workflow로 per-tier agent 스폰).

## 3. judge = GROUND-TRUTH 앵커 (CRITICAL)
- LLM judge에 **시스템 정답값(엔티티 수·알고리즘명·스택 등)을 주입**한다. 안 그러면 judge가 confident-wrong-number에 속는다.
- **핵심 교훈: 모델은 검색이 짚어주지 않은 구체값을 자신 있게 지어낸다.** retrieval이 약한 질의일수록 hallucination↑(특히 고능력 모델이 빈 곳을 메우려 날조). 그래서 GT 앵커 없는 LLM 평가는 신뢰 불가.

## 4. 결과 읽기 — 분리해서
- **retrieval 품질 vs gold-set 품질 분리**: hit@5가 낮아도, 검색이 *다른 적절한 노트*를 올렸는데 gold 목록이 좁아 'miss'로 찍힌 경우가 있다 → 그건 **벤치(gold) 재검토** 문제지 검색 실패 아님. spot-check로 구분.
- **모델 티어 선택(사용자 편의)**: 검색기반 Q&A 기본값은 보통 **중간 티어(sonnet급)** 가 sweet spot — 정확·근거·저환각·robust(검색 거부 0)이면서 최상위 티어보다 싸다. 최상위(opus급)는 깊은 합성에서만 우위, 검색이 약하면 오히려 날조로 붕괴할 수 있다. 최저가(haiku급)는 짧은 키워드를 "불명확"으로 되묻고 검색을 건너뛰기도.

## 5. 보강(튜닝) 규율
- 가중치/RRF/reranker 튜닝은 autoresearch로 **시간·라운드 박스**(예 ≤8R/≤90분), retrieval 지표(hit@k) 기준 개선만 promote.
- **score-gaming 거부**: 합성 composite만 오르고 hit@k가 떨어지는 후보는 거부(속도 단일 샘플 inflation 주의).
- **LLM 답변합성/전역 Map-Reduce 활성화**는 env-gate + 비용 상한 필수: 전역검색이 전체 커뮤니티에 LLM 호출 시 **상한(cap) 없으면 비용 폭주**(커뮤니티 수만큼 호출). 잘못된 timeout/provider 입력에 graceful fallback. 활성화 전 fallback 분기 테스트.
- **LLM provider 추상화 (단일 벤더 CLI에 못박기 금지)**: 합성 LLM 호출 경로는 **env로 provider 선택 가능하게 분기**(추상화)하고 기본은 OFF(opt-in). 특정 벤더의 print/headless CLI one-shot 모드(구독 인증 기반)는 **향후 deprecated·제한될 수 있으므로 그 경로 하나에 못박지 말 것** — 교체 가능한 plugin 구조 + 미설정/실패 시 template fallback 보존. 이러면 한 경로가 막혀도 다른 provider로 무중단 교체된다(default 동작은 opt-in OFF라 애초에 무영향).
  - ⚠️ **구독 CLI 자동화 = 벤더 미지원일 수 있음**: 구독 인증 기반 one-shot CLI(print/exec 모드)는 벤더가 **비대화 자동화를 공식 미지원**하는 경우가 있어(예고 없이 제한 가능). 따라서 이런 CLI provider는 **opt-in proof/local provider**로만 두고, 항상-켜는 production 합성이 필요하면 **벤더-지원 API key provider를 명시적 비용·키로 별도 추가**(운영자 결정 사항). 진짜 resilience는 "어느 CLI를 쓰느냐"가 아니라 **추상화 + OFF default + template fallback** 그 자체 — 어느 provider가 막혀도 기본 검색(retrieval)은 무영향.

## 6. 정직 framing
- "GraphRAG"를 쓴다고 MS GraphRAG 논문(arXiv:2404.16130) **동등**은 과장. LLM 관계추출·커뮤니티 LLM요약·전역 Map-Reduce가 실제 작동하는지 코드로 확인하고, 미작동이면 "GraphRAG 계열(graph-augmented RAG)"로 정직 표기.
- 개념 정확성: BM25≠단순 TF-IDF(TF 포화·길이정규화 핵심), RRF=점수 아닌 순위 융합, HNSW=근사(소규모엔 exact로 충분할 수 있음 — 적용 여부 코드검증).

## 참고 논문
RAG(Lewis 2020, arXiv:2005.11401) · BM25(Robertson & Zaragoza 2009) · DPR(Karpukhin 2020, 2004.04906) · HNSW(Malkov & Yashunin 2018, 1603.09320) · RRF(Cormack 2009) · cross-encoder(Nogueira & Cho 2019, 1901.04085) · GraphRAG(Edge 외 2024, 2404.16130) · RAGAS(Es 외 2023, 2309.15217).
