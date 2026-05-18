---
name: init
description: Use when the user runs /thiscode:init or first-time installs thiscode — detects env (vault state / tools / resources) and recommends an 8-Phase progressive install.
allowedTools: Bash, AskUserQuestion, Read
---

# init

> obsidian-cli → GraphRAG 점진 진행을 학생이 자연스럽게 따라가도록 wizard 형 install 진입점 (사용자 v2.1 spec).

## Repo-handoff contract (read first)

Shared, normative: `contracts/repo-handoff-install-contract.md` (in lockstep with
ThisCodex). In short:

**Default = interactive guided onboarding.** This `init` wizard asks one question
at a time; that is the default path for both humans and AI agents handed the
repo. If you are an AI agent: **run the guided wizard and relay each question to
the user** through your session/TUI — do **not** auto-run a non-interactive
install, do **not** self-answer or fabricate an answers file to skip questions,
and do **not** report "copied = installed" or placement as completed onboarding.
Use `--non-interactive` (and any CI / automation env) **only** on the user's
explicit opt-out, never as the default or step 1. On a missing required decision
the installer safe-stops with interactive recovery — relay that to the user and
let them choose; never self-answer to push past it.

## Prereq

- `jq` (JSON 처리)
- `python3` (Phase 추천 알고리즘)

## Workflow

1. **env detect** — `scripts/claude-discode-init.sh --detect-only --json` 호출, OS / vault / tools / resources 9 keys JSON 출력
2. **Phase 추천** — note_count + 도구 + 자원 multi-axis 알고리즘:
   - current: 현재 가능 (의무 install)
   - recommended: 권장 (사용자 y/n)
   - later: 조건 미충족 / advanced
3. **wizard 대화** — recommended Phase 별 `y/n` prompt, 사용자 선택 install dispatch
4. **install dispatch** — 선택한 Phase 마다 `scripts/install-*.sh` 호출
5. **healthcheck** — install 후 `bash scripts/healthcheck.sh`

## 8 Phase 매핑

(commands/init.md 참조)

## Non-interactive (CI/headless)

- `init.sh --non-interactive` → Phase 추천만, install skip
- `CLAUDE_DISCODE_INIT_AUTO=phase-X,phase-Y` env → auto install (prompt skip)

## 옵션 언제나 (사용자 spec Q2)

GraphRAG 노트 수 미충족 시도 사용자 force install 가능. preflight (Python/disk/port) 만 의무.
