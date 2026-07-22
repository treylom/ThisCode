---
description: thiscode 검색 환경 초기 설치 (Obsidian CLI / vault-search MCP / GraphRAG 서버)
allowedTools: Bash, AskUserQuestion, Write, Read
---

# /thiscode:km-bootstrap

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

Invokes the `knowledge-manager-bootstrap` skill — detects environment, prompts for vault_root + install matrix, runs install-*.sh scripts.

Use this command when:
- 처음 설치
- `/thiscode:search` 가 4-Tier 전부 실패 메시지 출력
- 머신 옮긴 후 환경 재구성
