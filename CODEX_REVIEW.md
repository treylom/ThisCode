---
title: thiscode Codex Adversarial Review (1차)
date: 2026-05-12
reviewer: codex:codex-rescue agent (id a75f7cff6c413cd71)
duration: 613s (14 tool uses, 44k tokens)
trigger: 사용자 회귀 지적 5건 (Codex 누락 / 공유 메모리 / 스레드 노하우 / 디버깅 / Claude Code 서버)
---

# Codex Adversarial Review — 1차 draft

> 본 보고서는 관리 봇이 신규 파일 작성 + install.sh 정정 + README 보강 단계의 plan doc.

## 회귀 4건 + 1건 (사용자 지적)

1. **Codex 검증 호출 누락** — install.sh 에 `codex --version` / `codex exec` 체크 없음. `/thiscode:start` checklist 가 claude · tmux · Discord 만 다룸.
2. **공유 메모리 4-tier 규칙 누락** — vault SHARED-INDEX.md 의 T1 (git-tracked shared) / T2 (machine-specific) / T3 (project-meetings) / T4 (per-bot WD) 분리 안 들어감.
3. **스레드 (회의) 노하우 부족** — 4-file 골격만, 핵심 누락: 출처 기반 cross-check / Discord REST API 패턴 / audience direct mention / 3 channel 병행 보고 / completion report 스레드.
4. **디버깅 24+ 카테고리 미매핑** — vault `agent-korea-daily/디버깅.md` 의 #1~#85 누적 회귀 DB, SHARED-INDEX.md 의 24+ 카테고리 (A-L) plugin 안에 chapter 매핑 안 됨.
5. **Claude Code 서버 기능 명시 누락** (추가 spec 10:41 KST) — `claude -p` 헤드리스 원샷 / MCP server / tmux session vs headless 분리 패턴.

## 회복 plan — 신규 파일 7건 + 정정 2건

### 신규 파일

1. **`commands/codex-check.md`** — `/thiscode:codex-check` slash
   - `codex --version` 검증
   - `codex login` 상태 확인
   - 모델 picker 확인 (gpt-5.5 표시)
   - ephemeral test (`codex exec --no-stream "ping"`)

2. **`skills/shared-memory/SKILL.md`** + `references/protocol.md`
   - T1-T4 4-tier 정책
   - 사용자 vault 있/없음 분기 (없으면 plain markdown folder)
   - SHARED-INDEX.md 형식
   - Read-before-Edit 의무 + 동시쓰기 방지

3. **`skills/meetings/SKILL.md`** + `references/protocol.md`
   - 4-file 표준 (00-context / 01-spec / 02-progress / 03-outcome)
   - **출처 기반 cross-check** (회의 신설 전 다축 grep)
   - **Discord REST API** thread 신설 (python urllib, POST /channels/{id}/threads type=11)
   - **audience direct mention** 의무 (텍스트만으로 부족)
   - **3 channel 병행 보고** (회의 outcome + 메인 채널 본문 + 발의 봇 mention)

4. **`skills/codex-exec-bridge/SKILL.md`**
   - vault `.claude/skills/codex-exec-bridge/` 6-file anatomy 재활용
   - `/tofu-at-codex` v2.2 패턴 (Leader=Opus / Workers=Sonnet+gpt-5.5 / DA=Codex adversarial)
   - subprocess `codex exec --no-stream --model gpt-5.5` 패턴
   - Hermes 환경에서도 동작 (코난 REPORT §4.3 subprocess plugin)

5. **`docs/03-shared-memory.md`** — 한국어 친절 톤 가이드 (4-tier + 사용 시나리오)

6. **`docs/06-claude-code-server.md`** ⭐ — 추가 spec
   - **`claude -p` 헤드리스 원샷** (launchd/cron, busy 내성)
   - tmux session vs headless 분리 패턴
   - DISCORD_STATE_DIR 환경변수 (봇 계정 분리)
   - 핵심 플래그: `-p` / `--model` / `--dangerously-skip-permissions` / `--no-session-persistence` / `< /dev/null`
   - 사용 시나리오: 봇 알림 / 정기 리마인드 / batch 작업

7. **`docs/08-debug-노하우.md`** — vault SHARED-INDEX.md + `agent-korea-daily/디버깅.md` 의 24+ 카테고리 chapter 매핑.

### 정정

8. **`install.sh`** Step 7 정정 + Step 5b 추가 (Codex CLI 검증)
   - `command -v codex` 체크 + 미설치 시 `npm install -g @openai/codex` 안내
   - `codex login` 상태 확인 (`codex auth status` 또는 `~/.codex/auth.json` 존재)
   - thiscode plugin install 안내 (`/plugin marketplace add treylom/ThisCode`)
   - 신규 슬래시 4종 안내 ( `/thiscode:start` / `:add-bot` / `:open-meeting` / `:self-update` / `:codex-check`)

9. **`README.md`** 정정
   - Claude Code 서버 기능 (headless + MCP) section 추가
   - Codex 호출 layer section 추가
   - 슬래시 5개 표 정정 (codex-check 추가)
   - 디버깅 노하우 + 공유 메모리 + 회의실 protocol → docs/ link

## vault 자산 재활용 경로 (확정)

| # | 자산 | 경로 |
|---|---|---|
| 1 | SHARED-INDEX.md (4-tier + 디버깅 24+) | `<vault>/AI_Second_Brain/.claude-memory/shared/SHARED-INDEX.md` |
| 2 | tofu-at-codex slash | `<vault>/.claude/commands/tofu-at-codex.md` |
| 3 | codex-exec-bridge skill (6-file) | `<vault>/.claude/skills/codex-exec-bridge/` |
| 4 | pumasi-config-spec | `<vault>/.claude/skills/pumasi-config-spec.md` |
| 5 | soul.md anatomy (6 봇) | `~/.claude/channels/discord-<bot>/soul.md` |
| 6 | 디버깅 DB #1~#85 | `<vault>/agent-korea-daily/디버깅.md` |
| 7 | headless claude pattern | `<vault>/AI_Second_Brain/.claude-memory/shared/reference_headless_claude_oneshot_pattern.md` |
| 8 | meetings 4-file 표준 | `<vault>/AI_Second_Brain/.claude-meetings/` |

## 검증 시나리오 (Codex 1차 권장)

1. **dry-run** — install.sh 의 각 step 을 사용자가 manual 로 따라가며 결과 확인
2. **fresh WSL sandbox docker** — Ubuntu 20.04 image 안에서 install.sh 실행
3. **Codex 2차 review** — 신규 파일들 작성 후 `codex review --base HEAD~1` 또는 codex:codex-rescue 재호출

## 작업 진행 순서 (관리 봇 본 plan 따라 정정)

- [x] Codex review 1차 받음
- [x] CODEX_REVIEW.md 저장 (본 파일)
- [ ] 신규 파일 7건 작성
- [ ] install.sh 정정
- [ ] README 정정
- [ ] 3rd commit + push
- [ ] Codex 2차 검증
- [ ] Discord 보고
