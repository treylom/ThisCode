# GLOSSARY — thiscode 용어집

> 가이드북 / docs / README 본문에서 첫 등장 시 본 GLOSSARY 의 해당 용어에 link 됩니다 (예: `[embedding](GLOSSARY.md#embedding)`).

## LLM 기본

### LLM
Large Language Model (대형 언어 모델) — GPT/Claude/Gemini 같은 텍스트 생성 AI.

### token
LLM 이 한 번에 처리하는 텍스트 단위. 영어는 ~4 char / token, 한국어는 ~2-3 char / token.

### context window
LLM 이 한 번에 기억할 수 있는 token 수. Claude Opus[1m] = 1M token (대화 1년치 분량).

### prompt
LLM 에게 주는 명령어 / 질문 text.

### completion
LLM 이 생성한 응답 text.

### temperature
LLM 응답의 무작위성 (0=결정적, 1=창의적). thiscode 검색 응답은 보통 0.2~0.5.

### embedding
단어 / 문장을 숫자 벡터로 변환한 표현. 예: "ARR" = [0.23, -0.45, 0.81, ...] (384-dim). 의미가 비슷한 단어는 벡터가 가까움.

### attention
transformer 모델의 핵심 — 입력 token 들 사이 어느 token 이 다른 token 에 영향 주는지 weight 매기는 메커니즘.

### transformer
2017 년 발표된 LLM 아키텍처 (Vaswani et al.). 현재 GPT/Claude/Gemini 모두 transformer 기반.

## 검색 기법

### semantic search
의미 검색. literal string match (예: "사과" → "사과" 만 찾음) 대신 의미 (예: "사과" → "과일/apple/Apple Inc." 도 후보).

### recall_at_K
top-K 검색 결과 중 정답 비율. recall@5 = 0.8 → 5개 중 4개가 정답.

### precision
검색 결과 중 정답 비율 (recall 과 다름). precision 우선 시 false positive 적음.

### F1
precision + recall 의 조화 평균. 단일 metric 으로 검색 quality 표현.

### fuzzy match
오타 / 변형도 매치. "saple" → "sample" 매치.

### literal match
정확히 같은 문자열만 매치 (ripgrep 의 default 모드).

### inverted index
단어 → 그 단어가 들어있는 문서 list 매핑. 검색 빠르게 하는 자료구조.

### knowledge graph (KG)
entity (개체) + relation (관계) 그래프. 예: NuriFlow --[CEO of]--> John.

### kg_depth
검색 결과 노드의 graph traversal 평균 depth. Tier 1 GraphRAG 만 의미 (다른 Tier = 0). 깊을수록 multi-hop 추론.

## RAG / GraphRAG

### RAG
Retrieval Augmented Generation — 검색 결과를 LLM 에게 context 로 주고 답변 생성.

### GraphRAG
RAG + knowledge graph 통합. Microsoft Research 가 2024 발표한 패턴. thiscode Tier 1 의 backbone.

### chunk
문서를 LLM context 에 들어갈 크기 (예: 500 token) 로 자른 단위.

### reranker
검색 결과를 LLM 으로 한 번 더 정렬. 빠른 vector search 후 정확한 LLM rerank.

## 도구

### MCP
Model Context Protocol — Anthropic 이 정의한 외부 도구 ↔ LLM 연결 표준. vault-search MCP = vault 안 검색 도구를 Claude Code 에 plug-in.

### CEL
Common Expression Language — Google 이 만든 식 평가 언어. Kubernetes / Envoy 등 사용. thiscode 의 `gates.expr` 의 evaluator 옵션.

### fixture
테스트용 미리 만든 데이터. benchmark/fixtures/queries.yaml = 20 query + expected hits.

### cohort
집단 / 코호트. 초기 사용자 cohort 같은 group. dogfood feedback 시 cohort 단위 분석.

### dogfood
"개 사료를 본인이 먹는다" — 본인이 만든 제품을 본인이 직접 사용해 검증.

## Plugin / Agent / Tier

### Tier
계층. km 플러그인의 4-Tier search fallback 계층 (검색 도구는 ThisCode 설치 스크립트로 설치; Tier 1=GraphRAG → Tier 2=Obsidian CLI → Tier 3=vault-search MCP → Tier 4=ripgrep).

### fallback
대체. 한 Tier 결과 부족 시 다음 Tier 시도.

### dispatcher
분배기. query 받아 적합한 Tier 호출하는 logic.

### skill
Claude Code 의 task 단위 정의 (`.claude/skills/<name>/SKILL.md`).

### agent
스킬 + 도구 + 모델 결합한 자율 실행 단위. `.agents/<name>.yaml` 로 정의 (v1.0 Custom Hybrid spec).

### hook
이벤트 발생 시 자동 실행되는 script (예: `SessionStart` 시 soul.md inject).

### plugin
Claude Code 에 등록되는 skill + command + hook 묶음.

### slash command
`/thiscode:init` 같은 명령. Claude Code 안에서 입력.

### YAML
"YAML Ain't Markup Language" — 사람이 읽기 쉬운 설정 파일 형식.

### Custom Hybrid (v1.0)
thiscode 의 agent spec 형식 — agentskills.io base + Hermes provides_* + 자체 extension.

### graduate (v1.0 → v1.1)
strict spec lock 후 dogfood feedback 받고 다음 major 로 upgrade.

## 관련 문서

- [AGENTS.md](AGENTS.md) — agent spec 5 Block 구조
- [BENCHMARK.md](BENCHMARK.md) — 5-axis 측정
- [ARCHITECTURE.md](ARCHITECTURE.md) — mermaid 차트
