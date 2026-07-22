---
description: thiscode vault 통합 검색 — 4-Tier (GraphRAG → Obsidian → MCP → grep)
allowedTools: Bash, Read, Glob, Grep, mcp__vault-search__*
---

# /thiscode:search

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

$ARGUMENTS

Invokes the `search` skill which runs Tier 1→4 per `contracts/search-fallback-4tier.md`.

## Flags
- `--quick` / `-q` → 3-5줄 즉답
- `--deep` / `-d` → 상세 분석
- `--no-moc` → MOC 우선 라우팅 제외

## Examples

```
/thiscode:search MCP란?
/thiscode:search --deep "GraphRAG vs Obsidian search 차이"
/thiscode:search --no-moc "specific note title"
```
