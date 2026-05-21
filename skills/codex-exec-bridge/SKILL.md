---
name: codex-exec-bridge
description: Use when needing codex-exec-worker 브리지 에이전트 실행 프로토콜 — CLI 호출, 상태 파일, 게이트 검증, 에러 복구, 팀 통신
disable-model-invocation: true
---

# Codex Exec Bridge — Execution Protocol (Entry Point)

> pumasi-job-worker.js 패턴을 codex-exec-worker 에이전트에 통합.
> codex CLI를 샌드박스 없이 실행하고, 상태 파일로 추적하며, Dynamic Gate로 결과를 검증합니다.

---

## 서브파일 목록

| 파일 | 내용 | 섹션 |
|------|------|------|
| [01-cli-invocation.md](01-cli-invocation.md) | Codex CLI 기본 호출, reasoning effort, 플래그, 타임아웃 | §1 |
| [02-status-file.md](02-status-file.md) | 상태 파일 프로토콜 (위치, atomic write, 상태 머신) | §2 |
| [03-dynamic-gate.md](03-dynamic-gate.md) | Dynamic Gate 통합 (순서, 결과 형식, FAIL 흐름) | §3 |
| [04-error-recovery.md](04-error-recovery.md) | 에러 복구 (autofix 프롬프트, 재시도 예산, 에스컬레이션) | §4 |
| [05-team-communication.md](05-team-communication.md) | Agent Teams 통신 (SendMessage, progress, TaskUpdate, 전체 흐름) | §5 |

---

## 전체 실행 흐름 요약

```
1. 태스크 수신 (SendMessage from lead)
2. progress 0% 업데이트
3. pending 상태 파일 작성 (atomic write)
4. codex exec 실행 (timeout 300s)
5. running 상태 파일 업데이트
6. progress 50% 업데이트
7. Dynamic Gate 실행 (tsc → build → test → lint)
8. PASS: report.json 작성 → SendMessage(lead, done) → TaskUpdate(completed)
9. FAIL: autofix 프롬프트 생성 → codex exec 재실행 (최대 2회)
10. 모든 재시도 실패: SendMessage(lead, escalation) → progress 100%
```

## 참조 파일

| 파일 | 역할 |
|------|------|
| `.claude/skills/dynamic-gate-verification.md` | 게이트 파이프라인 상세 명세 |
| `pumasi-job-worker.js` lines 67-71 | atomicWriteJson 구현 |
| `pumasi-job-worker.js` lines 273-314 | 타임아웃/종료 처리 |
| `pumasi-job.js` lines 723-762 | 게이트 실행 루프 |
| `pumasi-job.js` lines 946-1007 | 재위임 컨텍스트 빌더 |

---

## How to Use This Skill

Use this skill when you need to execute tasks through the Codex CLI bridge with sandboxed execution, state tracking, and dynamic gate verification. It handles multi-model execution (reasoning effort), error recovery with autofix, and team communication via Agent Teams.
