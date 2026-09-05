---
title: thiscode Codex Adversarial Verify (2nd round)
date: 2026-05-12
reviewer: codex review --base HEAD~7 (gpt-5.5) + orchestrator-bot self-review (Claude Code docs cross-check)
commits_reviewed: 7 (732ed4c → f5ad7d6)
verdict: ❌ Needs fixes (3 critical/high)
---

# Codex Adversarial Verify — 2nd round

> 본 verify = `codex review --base HEAD~7` PR diff review (gpt-5.5) 2 finding + orchestrator-bot self-review (Claude Code 공식 docs cross-check) 1 finding 통합. 1차 review (CODEX_REVIEW.md) 회복 후 잔존 critical 점검.

## CRITICAL (blockers, must fix before user-facing)

### C1. Slash 7 frontmatter key 회귀 — `allowedTools` (camelCase) → `allowed-tools` (kebab-case)

**근거**: Claude Code 공식 docs `Frontmatter reference` 표 (https://code.claude.com/docs/en/slash-commands):

> `allowed-tools` | No | Tools Claude can use without asking permission when this skill is active. Accepts a **space-separated string** or a YAML list.

**우리 현 상태** (7 파일 전부 회귀):
- `commands/start.md:3` — `allowedTools: Bash, Read, Write, Edit, AskUserQuestion, Skill`
- `commands/install-hooks.md:3` — `allowedTools: Bash, Read, Write, Edit, AskUserQuestion`
- `commands/create-bot.md:3` — `allowedTools: Bash, Read, Write, AskUserQuestion`
- `commands/add-bot.md:3` — `allowedTools: Bash, Read, Write, Edit, AskUserQuestion`
- `commands/open-meeting.md:3` — `allowedTools: Bash, Read, Write, AskUserQuestion`
- `commands/codex-check.md:3` — `allowedTools: Bash, Read, AskUserQuestion`
- `commands/self-update.md:3` — `allowedTools: Bash, Read`

**2중 회귀**:
1. key 명 camelCase → spec 안 kebab-case
2. value comma-separated → spec 안 space-separated string 또는 YAML list

**Fix**: 7 파일 전부 `allowed-tools: Bash Read Write Edit AskUserQuestion Skill` (space-separated) 또는 YAML list 양식. 본 회복 안 하면 Claude Code 가 7 slash 전부에서 permission prompt 매번 발생 (사용자 경험 손상).

### C2. SessionStart hook 안 `claude -p` 재귀 invoke (Codex P1)

**근거**: Codex review 안 직접 인용:
> If a user follows this optional SessionStart hook, starting Claude runs `claude -p`, which starts another Claude process that reads the same settings and fires SessionStart again. That can recurse until timeouts/process limits instead of performing a lightweight update check.

**위치**: `commands/self-update.md:92` — `"command": "claude -p '/thiscode:self-update'"`

**메커니즘**: 사용자가 본 hook 등록 → claude 진입 → SessionStart fire → `claude -p` 실행 → 자식 process 가 같은 settings.json 읽음 → 다시 SessionStart fire → 무한 재귀 / 프로세스 한도 초과.

**Fix**: hook 안 `claude -p` 대신 bash script 직접 호출 (예: `cd <vault> && git fetch && git rev-list HEAD..origin/main --count`). 또는 SessionStart hook 권장 자체 제거 + 사용자 manual 호출만 권장.

## HIGH (regression risk, should fix)

### H1. UserPromptSubmit hook dedupe 누락 (Codex P2)

**근거**: Codex review 안 직접 인용:
> When `/thiscode:install-hooks` is run more than once, this merge appends a fresh UserPromptSubmit entry every time while only SessionStart is deduped. In that scenario the slash detector and regression self-check run repeatedly for every prompt, duplicating injected context/output and making the command noisy.

**위치**: `commands/install-hooks.md:94` — jq merge 안:
이 인용은 당시 리뷰 기록이다. 현재 `/thiscode:install-hooks`는 `skills/install-hooks/SKILL.md`에 있는 스킬이며, 별도 command 파일은 제공하지 않는다.

```jq
.hooks.SessionStart = ((.[0].hooks.SessionStart // []) + (.[1].hooks.SessionStart // []) | unique_by(.hooks[0].command))
.hooks.UserPromptSubmit = ((.[0].hooks.UserPromptSubmit // []) + (.[1].hooks.UserPromptSubmit // []))   # ← unique_by 누락
```

**Fix**: UserPromptSubmit 도 SessionStart 와 같이 `unique_by(.hooks[0].command)` 적용. install-hooks 재실행 시 hook 중복 차단.

## MEDIUM (improvement)

### M1. Slash 7 frontmatter — `description` 필드 다 있음 OK, `disable-model-invocation` 권장 추가

본 7 slash 는 wizard 성격 (사용자 명시 invoke). Claude 자동 invoke 차단 권장. spec:

```yaml
disable-model-invocation: true
```

위치: 7 commands/*.md frontmatter 전부.

### M2. install.sh 함수 정의 순서

`main()` 안 line 286-292 에서 `install_codex_cli` + `install_obsidian_cli` 호출, 정의는 line 360+ / 300+. Bash 는 함수 lookup 을 call time 에 하므로 본 패턴 동작 OK. 다만 가독성 위해 함수 정의를 main() 위로 이동 권장.

## LOW / suggestion (style, future-proof)

### L1. plugin.json + marketplace.json schema 검증

본 verify 안 plugin.json / marketplace.json 직접 inspect 안 함. 차회 verify 영역.

### L2. hooks/ shebang macOS/Linux 호환

3 hook script `#!/usr/bin/env bash` 사용 — macOS / Linux 양쪽 OK. zsh 사용자 환경에서도 bash 강제. portability OK.

### L3. Security — install.sh sudo

Step 2 안 `sudo apt-get install` 등. 사용자 sudo 권한 명시적 prompt 없음. install.sh 가 `curl | bash` 권장 패턴이므로 사용자가 source 확인 후 실행 가정. README 안 `chmod +x` 안내 + sudo prompt 가 발생할 수 있음 명시 권장.

## Verdict

❌ **Needs fixes** — 3 critical/high (C1 + C2 + H1) 필수 회복.

회복 후 ✅ Ready to ship 전환.

## 변경 이력

- 2026-05-12 23:50 KST: 본 2차 verify 작성 (orchestrator-bot self-review + codex review --base HEAD~7 통합). 8th commit 으로 회복 진행.
