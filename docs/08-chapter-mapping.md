---
title: 학습 경로 매핑 — 디버깅 노하우 30+ 카테고리
order: 8
date: 2026-05-13
status: draft (v0.2.0)
---

# 학습 경로 매핑

> SHARED-INDEX.md 30+ 디버깅 학습 + thiscode 어제 회의 §5 spec 을 학습 경로 구조로 정리. Phase 1/2/3 × 학습 곡선.

## Phase 1 — 입문 (학생이 첫 봇을 띄움)

> 목표: 봇 1개 작동 + 사용자 안전 + 기본 협업 룰 체득.

### C1. Discord 봇 응답 게이트 — 채널에 reply, 터미널만 X
- 학습: 외부 채널 응답 task 에서 reply 도구 우선. 터미널 출력만 = 사용자에게 안 보임.
- 회귀 case (학습 narrative): 2026-04-30 + 2026-05-04 orchestrator-bot × 2회 회귀.
- 영상 길이: 8-10 min.

### C2. 단정 표현 lint — "절대/반드시/금지" cross-check
- 학습: hard rule 작성 전 다른 봇 cron-registry / 운영 사례 cross-check 의무.
- 회귀 case: 2026-05-05 CronCreate "절대 금지" 단순화.
- 영상 길이: 6-8 min.

### C3. 막혔을 때 사용자 묻지 말고 스킬 시도
- 학습: `/km:search` / `/autoresearch` 로 끝까지 시도 후 보고. A/B/C/D 4지선택 안티패턴.
- 영상 길이: 7 min.

### C4. 응답 echo drift 차단
- 학습: 짧은 어휘 5회+ 반복 X. 자기 응답 재학습 token 강화 회로 차단.
- 회귀 case: 2026-05-11 Manus 봇 200+ 회 "영영" placeholder 사고.
- 영상 길이: 5-6 min.

## Phase 2 — 중급 (워커 봇 + 공유 memory + 회의실 + km/search)

> 목표: 다 봇 운영 + vault 정규화 + 회의 protocol + km/search 통합.

### C5. vault path 양쪽 root 동시 점검
- 학습: git repo `020-Library/` ≠ Mac vault `Library/` (rsync 시점 prefix strip). file system fact 양쪽 grep 의무.
- 영상 길이: 8 min.

### C6. 회의실 vault protocol (audience N 분기)
- 학습: 0 봇 = T1 shared/ 직접, 1 봇 = outcome-only.md, ≥2 봇 = Full 4-file (00-context / 01-spec / 02-progress / 03-outcome).
- 영상 길이: 10-12 min.

### C7. session clear 회복 — 3축 시너지
- 학습: Discord chat archive + Obsidian vault + SessionStart 자동 주입 셋 다 필요.
- 영상 길이: 9 min.

### C8. MOC-Map 진입점 + GraphRAG 4-Tier search
- 학습: thiscode 4-Tier (GraphRAG → Obsidian CLI → vault-search MCP → ripgrep). MOC 우선 라우팅.
- contract: `contracts/search-fallback-4tier.md` v0.1.0.
- 영상 길이: 12-15 min.

### C9. KM Mode I/R/G + variant lite/at/plain
- 학습: variant matrix per `contracts/km-variant-matrix.md`. lite (Phase 1·2 default) / at (Agent Teams) / plain (headless).
- 영상 길이: 10 min.

### C10. 4-Tier search drift 감지 (km-version.sh)
- 학습: thiscode contract ↔ vault mirror version 비교. SessionStart hook 으로 warning.
- 영상 길이: 5 min.

## Phase 3 — 심화 (Agent Teams + Codex + 자가 업데이트 + 운영)

> 목표: 다 봇 24/7 운영 + Codex 워커 분산 + 자가 검증.

### C11. 코드 점검 GPT-5.5 (Codex) 페어 + DA 동반 스폰
- 학습: 모든 코드 변경 단독 Claude X. `/pumasi` 또는 `/codex:rescue` 로 Codex 페어. DA(adversarial reviewer) 동반.
- 영상 길이: 11 min.

### C12. 워커 spawn 룰 — model="sonnet" 명시 의무
- 학습: Agent() 호출 시 model 미지정 → Opus 4.7 inherit (비용 폭증). 항상 명시.
- 영상 길이: 5 min.

### C13. CCProxy 다발 워커 + /pumasi orchestrator
- 학습: 워커 다발 호출은 CCProxy 띄우고. Standard mode fallback 금지. /pumasi 안정성 ↑.
- 영상 길이: 10 min.

### C14. SoP X — Lead 단계 진입 cross-check 의무
- 학습: 다음 단계 진입 시 직전 산출 cross-check 결과 명시. silent 진입 회귀 차단.
- 영상 길이: 8 min.

### C15. SoP Y — 회의 primary + secondary DA cross-check
- 학습: verdict 합성 시 primary DA (외부) + secondary DA (내부) 의무. 단일 DA 회귀 risk 차단.
- 영상 길이: 9 min.

### C16. cron 분류 — launchd vs CronCreate vs CCR
- 학습: 정시 critical → launchd + tmux send-keys / 세션 의존 watchdog → CronCreate / CCR → 사용자 정책에 따라 금지/허용.
- 영상 길이: 12 min.

### C17. declarative → procedural enforcement 갭
- 학습: hard rule 메모리만으로는 attention decay → 회귀. UserPromptSubmit hook 으로 procedural pre-response gate.
- 영상 길이: 10 min.

### C18. aktofu-bot Phase A → Phase B Stop hook auto-trigger
- 학습: Lead 응답 분할 회귀를 Stop hook chain 으로 catch. heartbeat 7-step filter.
- 영상 길이: 11 min.

### C19. 봇 self-skill 영역 R&R
- 학습: `/strange` · `/aktofu` · `/karpathy` 통합 허브 스킬 변경 시 봇 본인이 초안, Karpathy 검토·commit.
- 영상 길이: 7 min.

### C20. Discord 봇 mention 다축 channel reference fetch
- 학습: 봇 위치 단정 전 reference doc + 어벤져스 + 멀티버스 채널 3축 cross-check 의무.
- 영상 길이: 8 min.

## 보조 + 운영 카테고리 (Phase 1-3 분산)

### C21. 일정·메일 — gws CLI primary, MCP fallback
- 학습: Calendar / Gmail MCP 헤드리스 OAuth 실패 + 인덱스 지연 회피. gws 0.22.5 우선.
- 영상 길이: 6 min.

### C22. negative instruction word leak — cron prompt
- 학습: cron LLM prompt 에서 금지 단어 직접 사용 시 leak 위험. positive instruction (출력 첫 줄 형식 강제).
- 영상 길이: 5 min.

### C23. No-auth 우회 금지 — OAuth 2.1 + DCR 디폴트
- 학습: 외부 노출 MCP / API 단기 편의로 No-auth 후퇴 금지.
- 영상 길이: 7 min.

### C24. 카톡 1인 카톡방 — 외부 시연 익명성
- 학습: 라이브 시연 시 실제 오픈카톡방 X → 1인 카톡방 (나 자신과의 대화). 동작 동일 + privacy 클리어.
- 영상 길이: 4 min.

### C25. AI agent 진행 시간 기준 — 남은 시간 산정
- 학습: 사람 시간 X. AI agent 사이클·step·active 시간. 외부 deadline 자체는 fact 명시 OK.
- 영상 길이: 5 min.

### C26. vault archive 폴더 정책
- 학습: `_archive-*` / `_attachments` prefix 폴더 = 모든 검색·인덱싱 도구 exclude. GraphRAG 자동 + 다른 도구 수동.
- 영상 길이: 5 min.

### C27. 회의 audience 자가 점검
- 학습: 회의 폴더 신설 전 실제 audience 봇 수 자가 점검. 라벨링 X, 실제 발의 ✓.
- 영상 길이: 6 min.

### C28. follow-up — schedule-bot 캘린더 등재 의무
- 학습: hard timing follow-up 발생 시 040-Schedule/ owner schedule-bot mention 등재 의무.
- 영상 길이: 5 min.

### C29. "긴급" 워딩 over-stack 방지
- 학습: structure-level guard 1중 충분 vs LLM-side guard 다중 redundant stack 안티패턴.
- 영상 길이: 7 min.

### C30. typst-report Windows vault 동시 복사
- 학습: WSL 경로 + `/mnt/c/Users/...` 동시 복사 의무 (운영자 Obsidian 리뷰 위함).
- 영상 길이: 4 min.

## 영상 총량 추정

- Phase 1: 4 chapter × 평균 7 min = ~28 min
- Phase 2: 6 chapter × 평균 9 min = ~54 min
- Phase 3: 10 chapter × 평균 9 min = ~90 min
- 보조: 10 chapter × 평균 5.5 min = ~55 min

**합계: ~227 min (3 시간 47 분)** — 마스터시트 가이드 "약 15 시간" 의 25% 분량 (디버깅·운영 노하우 슬롯). 나머지 75% 는 KM/search 흐름 + Agent Teams 실습 + 실습 프로젝트.

## Cross-reference

- vault SHARED-INDEX.md — 본 카테고리의 fact source
- `contracts/{search-fallback-4tier, km-mode-spec, km-variant-matrix}.md` — Phase 2-3 핵심 spec
- 어제 회의 03-outcome.md §5 — thiscode plugin spec 의 영상 mapping 초안
- 본 사이클 outcome (`AI_Second_Brain/.claude-meetings/2026-05-12-thiscode-plugin/03-outcome.md` 2026-05-13 followup)

## 잔존 작업 (chapter 본문 실제 작성)

본 문서 = chapter index. 각 chapter 본문 (slide outline + 실습 script + 영상 녹화 cue) 은 별도 사이클. GPT-5.5 병렬 spawn 으로 chapter 별 outline draft 생성 가능.

— Karpathy
