---
description: thiscode knowledge-manager 진입점 — variant 자동 라우팅 (lite/at/plain)
allowedTools: Read, Write, Bash, AskUserQuestion, WebFetch, Glob, Grep
---

# /thiscode:km

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

$ARGUMENTS

## Variant routing

1. Parse `$ARGUMENTS` for `--variant lite|at|plain` flag.
2. If absent:
   - $CLAUDE_DISCODE_HEADLESS=1 → variant = plain
   - "아카이브 정리" / "카테고리 재편" / "그래프 구축" keywords → variant = at
   - else → variant = lite (Phase 1·2 default)
3. Invoke the matching skill via `Skill` tool:
   - `knowledge-manager-lite` / `knowledge-manager-at` / `knowledge-manager-plain`
4. If skill emits "config missing" → invoke the `knowledge-manager-bootstrap` skill.

## Examples

```
/thiscode:km https://example.com/article
/thiscode:km --variant at "아카이브 정리: 020-Library/Research"
/thiscode:km --variant plain "이 텍스트 저장: ..."
```
