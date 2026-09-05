---
description: thiscode 환경 감지 + 8 Phase 로컬 도구 안내 (사용자 v2.1 spec)
allowedTools: Bash, AskUserQuestion, Read
---

# /thiscode:init

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

$ARGUMENTS

## Purpose

vault 상태 / OS / 도구 / 자원 감지 → 8 Phase progressive journey 추천 (현재 가능 / 권장 / 나중). 사용자 y/n 선택 후 에이전트가 선택한 ThisCode 스크립트를 실행한다.

## 8 Phase 진행 (Phase 0~7, 사용자 v2.1 spec)

| Phase | trigger | install |
|---|---|---|
| 0 | vault 미설치 | Obsidian app (link 안내) |
| 1 | vault 시작 | ThisCode `scripts/install-ripgrep.sh` (ripgrep, Tier 4) |
| 2 | Zettelkasten 시도 | ThisCode `scripts/install-obsidian-cli.sh` (Obsidian CLI, Tier 2) |
| 3 | 100+ 노트 의미 검색 갈증 | ThisCode `scripts/install-vault-search.sh` (선택적 로컬 vault-search MCP) |
| 4 | 500+ 권유 / 1000+ strong / 옵션 언제나 | ThisCode `scripts/install-graphrag.sh` (GraphRAG, Tier 1) |
| 5 | 2000+ 노트 혼란 | km 플러그인 `/km:knowledge-manager-at` 의 Mode R preflight (Claude Code 전용 — Codex는 km 플러그인 문서를 따름) |
| 6 | 3000+ + GraphRAG installed | Dashboard 시각화 (선택, 외부 link) |
| 7 | advanced | 하이브리드 4채널 (선택, Journey-12/13) |

위 표의 Tier 번호는 ThisCode가 설치·점검하는 로컬 도구 단계입니다. km
플러그인의 `/km:search`는 GraphRAG → Obsidian CLI → Obsidian MCP → text
search 순서로 별도 실행하며, `vault-search MCP`는 이 fallback의 Tier가 아닙니다.

## Flow

1. `bash $CLAUDE_DISCODE_HOME/scripts/claude-discode-init.sh` 실행 — env detect + Phase 추천 + interactive prompt
2. 감지 스크립트 자체는 검색 Tier를 설치하지 않는다. 사용자가 y를 선택한 Phase마다 에이전트가 해당 ThisCode 로컬 스크립트를 실행한다:
   - phase-1-ripgrep → `scripts/install-ripgrep.sh --apply`
   - phase-2-cli-install → `scripts/install-obsidian-cli.sh`
   - phase-3-mcp → `scripts/install-vault-search.sh --apply`
   - phase-4-graphrag / strong → `scripts/install-graphrag.sh --apply`
3. `/km:search`는 검색 fallback을 실행하고 `/km:setup`은 km 저장 위치·MCP·설정을 구성한다. `/km:setup`은 검색 Tier 설치 명령이 아니다.
4. phase-5-mode-r-preflight → km 플러그인 `/km:knowledge-manager-at` 의 Mode R preflight (Claude Code 전용 — Codex는 km 플러그인 문서를 따름) (read-only 진단 — km 미설치면 README 의 km 설치 포인터 안내)
5. 완료 후 healthcheck 실행

## Fallback

CI/headless 환경:
- `--non-interactive` flag → Phase 추천만 출력
- `CLAUDE_DISCODE_INIT_AUTO=<phase1>,<phase2>` env → auto install (prompt skip)

## 옵션 언제나 제공 (사용자 spec Q2)

GraphRAG 가 vault 노트 수 < 500 인 경우에도 `--force-phase phase-4-graphrag` flag 또는 wizard 안 "옵션 강제 진행" 선택지로 install 가능. preflight (Python 3.10+ / disk 5GB+ / port 8400) 통과만 의무.
