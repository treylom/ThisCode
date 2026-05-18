# 08. 디버깅 노하우 — 24+ 카테고리

> thiscode 운영 노하우 핵심 자산. vault SHARED-INDEX.md + `agent-korea-daily/디버깅.md` #1~#85 누적 회귀 DB 기반.

## 카테고리 분류

| Cat | 영역 | 회귀 예시 |
|---|---|---|
| **A** | Workflow / Tooling | cron 분류 (launchd vs CronCreate vs CCR), hook 등록, 자기 스킬 영역 |
| **B** | Code Review | GPT-5.5 페어, CCProxy, DA 동반 스폰, `model="sonnet"` 명시 |
| **C** | Vault Path | 정규화, 양쪽 root 동시 grep, archive exclude |
| **D** | 회의 protocol | SOURCE FACT cross-check, audience direct mention, 3-channel 병행 |
| **E** | Security | No-auth 우회 금지, OAuth 우선 |
| **F** | Time / Demo | AI agent 진행 시간 기준, 1인 카톡방 익명성 우회 |
| **G** | Output Sync | typst-report Windows vault 복사 |
| **H** | LLM Prompt | negative instruction word leak |
| **I** | Schedule / Email | gws CLI 우선 (MCP fallback) |
| **J** | Plugins | codex CC plugin, Hermes 호환, discord 봇간통신 drop, 봇별 OAuth 초대 |
| **K** | External Apps | 카카오톡 FOCUS_FAIL, NotificationCenter overlay, 한글 입력 깨짐 |
| **L** | Cross-bot SoP | Lead cross-check, dual DA cross-check |

각 카테고리에 vault 의 실제 메모리 파일 / 디버깅 케이스 link.

---

## A. Workflow / Tooling

### A-1. cron 등록 분류 (3-tier)

| 잡 성격 | 권장 경로 | 이유 |
|---|---|---|
| 정시 critical (예: 매일 9시 보고서) | launchd + tmux send-keys 또는 `claude -p` | 시스템 레벨, 가장 안정 |
| 세션 의존 watchdog·health | CronCreate (CC 세션 내부) | 세션 안 작업 |
| 외부 CCR (RemoteTrigger) | 일반적으로 비추천 | 로컬에서만 진행 권장 |

회귀: 2026-05-05 "CronCreate 절대 금지" 단순화 → 다른 봇 cron-registry cross-check 후 nuance 정정. (단순화 회귀)

### A-2. UserPromptSubmit hook 의 self-check 표

declarative hard rule 만으로는 attention drift 시 회귀 발생. UserPromptSubmit hook 의 4-gate stdout 주입 → procedural pre-response gate 강제.

회귀 case 4종:
- Discord reply gate (터미널만 출력)
- 단정 표현 lint ("절대/반드시")
- single-grep trap (vault fact 단일 grep)
- skill invoke gate (brainstorming skip)

### A-3. 봇 self-skill 영역 R&R

`/strange`, `/aktofu`, `/karpathy` 통합 허브 스킬 변경 시 봇 본인이 초안, Karpathy 가 검토·commit. design 사전 제시 redundant.

---

## B. Code Review

### B-1. GPT-5.5 (Codex) 페어 의무

모든 코드 변경 시 단독 Claude ❌. `/pumasi` 또는 `/codex:rescue` 또는 `codex exec` 으로 Codex (gpt-5.5) 페어링. DA (adversarial reviewer) 동반 스폰.

### B-2. CCProxy 다발 워커

kill-switch 는 spawn 경로 GAP 때문. CCProxy 자체는 건강. 비코딩 워커 다발 호출은 CCProxy 띄우고 사용. Standard mode 로 폴백 금지.

### B-3. `model="sonnet"` 명시 의무

Agent() 호출 시 model 미지정 → Opus 4.7 inherit (비용 폭증). 항상 `model="sonnet"` 명시. orchestrator 워커는 sonnet, codex exec 는 gpt-5.5.

### B-4. DA 동반 스폰 의무

워커 작업 시 항상 DA (adversarial reviewer) 함께 스폰. 워커 완료 + 통합 게이트만으로 sign-off ❌. ACCEPTABLE / CONCERN / BLOCKING 3 단계.

### B-5. No silent fallback

명시 모델 안 되면 default 자동 폴백 ❌. CLI 업그레이드 / CCProxy / SDK / alias 전수 점검 후 보고.

---

## C. Vault Path

### C-1. 정규화 + 양쪽 root 동시 grep

git repo `020-Library/` ≠ Mac vault `Library/` (rsync 시점 prefix `020-` strip). file system fact 검증 시 양쪽 root 동시 grep 의무.

회귀: 2026-05-11 코난 cross-bot 검증 false negative ("Mac vault sync 미반영" 보고) → AK-Tofu 정정.

### C-2. Archive 폴더 정책

`_archive-*` / `_attachments` prefix 폴더 = 모든 검색·인덱싱 도구 exclude. GraphRAG 자동 + 다른 도구 수동 후처리.

---

## D. 회의 protocol

자세히는 [05-meeting-thread-protocol.md] 참조.

- D-1. SOURCE FACT cross-check (다축 grep) 의무
- D-2. audience direct mention (텍스트만 ❌)
- D-3. 3-channel 병행 보고 (회의 outcome + 어벤져스 본문 + 발의 봇 mention)

---

## E. Security

### E-1. No-auth 우회 금지

외부 노출 MCP/API 는 단기 편의로 No-auth/단순 Bearer 후퇴 ❌. OAuth 2.1 + DCR + scope 세분화 디폴트. 검증도 stdio/localhost.

---

## F. Time / Demo

### F-1. AI agent 진행 시간 기준

모든 봇·모든 프로젝트 남은 시간 산정 시 사람 시간 ❌, AI agent 사이클·step·active 시간 단위. 외부 deadline 자체는 fact 명시 OK, "남은 시간" 만 AI agent 단위.

### F-2. 1인 카톡방 익명성 우회

외부 청중 라이브 시연 시 실제 오픈카톡방 ❌ → 1인 카톡방 (나 자신과의 대화) 사용. 파이프라인 변경 없이 동일 동작 + 익명성 클리어.

---

## H. LLM Prompt

### H-1. Negative instruction word leak

cron LLM prompt 에서 금지 단어 직접 사용 시 해당 단어 output leak 위험. "test"·"ping" 직접 명시 → Sonnet 4.6 이 trigger 로 사용해 "test ping" + 본문 2발 동시 발송.

방지: positive instruction (출력 첫 줄 형식 강제 ⏰/📋) + 의미만 표현.

---

## I. Schedule / Email

### I-1. gws CLI 우선 (Calendar/Gmail MCP fallback)

Calendar MCP 헤드리스 OAuth 실패 + Gmail MCP 검색 인덱스 지연 사고 회피. 모든 봇 일정·캘린더·이메일 작업 gws CLI primary.

회귀: 2026-05-05 Strange Gmail MCP 4번 시도 회귀 catch.

---

## J. Plugins

### J-1. plugin update 시 hook patch 회귀

봇 간 mention 통신이 plugin 안에 들어 있을 때, plugin update 한 번이면 그 채널이 silently 끊김. 사용자가 인지 못 하면 "왜 봇끼리 답이 없지" 디버깅 무한루프.

### J-2. discord MCP `msg.author.bot` 전면 drop → 봇간통신 불가 (2026-05-18 WSL 핸드오프)

**증상**: 다봇 협업 채널에서 서로의 메시지를 못 읽음. access.json allowlist 에 봇 ID 전부 등재돼 있어도 무응답.

**근본 원인** (코드 확정, 추측 ❌): 공식 discord 플러그인 `…/external_plugins/discord/server.ts` (≈L806):
```js
client.on('messageCreate', msg => {
  if (msg.author.bot) return   // gate() allowlist 검사 전에 봇 메시지 전부 폐기
  handleInbound(msg)...
```
봇 발신 메시지는 `gate()` 도달 전 폐기 → allowlist 무관 (single-axis "allowlist 문제" 가설 기각, 코드 read 로 확정).

**해결 recipe**: blanket drop → 3-가드 교체.
- `msg.author.id === client.user?.id` → 차단 (자기-루프 hard guard, 유지 필수)
- `msg.webhookId` → 차단 (스팸 surface 유지)
- `msg.author.bot && DM` → 차단 (봇 페어링 코드 spew 방지)
- 그 외 그룹 채널 타봇 메시지 → 통과 → 기존 `gate()` 의 채널 allowlist + `requireMention` 이 스코프 (멘션 시에만 wake = 루프 브레이크)

**⚠️ 재적용 노트 (J-1 의 실현 사례)**: 이 파일은 `~/.claude/plugins/marketplaces/claude-plugins-official/external_plugins/discord/server.ts` = **ThisCode 레포 밖 공식 플러그인**. plugin update / `/plugin marketplace update` 시 **덮어쓰임** → 끊기면 본 J-2 패치 재적용. 영구화(외부 패치 레이어 / post-update hook)는 아키텍처 결정 사안 (spec `docs/2026-05-18-repo-handoff-interactive-default-design.md` §J-2 참조).

**검증 상태**: `bun server.ts` 핫리로드 아님 → 패치는 MCP 게이트웨이(전봇) 재시작 후 반영. 재시작·봇간 @멘션 수신 = 사용자 라이브 테스트 (verification-before-completion: 재시작 전 "해결됨" 단정 보류).

### J-3. 봇별 OAuth 초대 누락 = 무반응 1순위 원인 (2026-05-18 WSL 핸드오프)

**증상**: 신규 봇 무반응. 로컬 설정(토큰·access.json·soul.md)은 다른 정상 봇과 동일한데 인바운드 0건.

**근본 원인**: Discord 는 "사용자와 같은 서버를 공유하는 봇하고만 DM 가능". **봇마다 별도 Discord 애플리케이션 → OAuth 초대도 봇별로 따로** 필요. 다봇 셋업에서 신규 봇 초대를 빠뜨리면 그 봇만 메시지 미도달. (로컬은 처음부터 정상이므로 토큰·코드 디버깅은 시간낭비 — 초대부터 확인.)

**무반응 진단 순서** (토큰 비노출, 읽기전용 API — 사용자 사전 승인 후):
```bash
TOKEN=$(grep -m1 DISCORD_BOT_TOKEN "$BOT_DIR/.env" | cut -d= -f2-)
curl -s -H "Authorization: Bot $TOKEN" https://discord.com/api/v10/users/@me            # 200 = 봇 토큰 정상 (어느 봇인지 확인)
curl -s -H "Authorization: Bot $TOKEN" https://discord.com/api/v10/users/@me/guilds     # 소속 서버 0개 = 미초대 (= 근본원인)
curl -s -H "Authorization: Bot $TOKEN" https://discord.com/api/v10/channels/<CHANNEL_ID> # 200 = 해당 채널 접근 가능
```
`/users/@me/guilds` 가 빈 배열 = **서버 미초대 확정** → create-bot/start 의 OAuth URL 로 재초대 → 봇 패널 `tmux respawn-pane -k` 재시작(새 guild 인식). 그래도 무반응이면 2순위 = 봇 앱 Gateway Intent(Message Content) 미설정.

---

## K. External Apps

### K-1. 카카오톡 FOCUS_FAIL

카카오톡이 채팅 탭이 아닌 다른 탭에 있음 → `Could not focus search field`. 해결: 채팅 탭 강제 전환 osascript 우선.

### K-2. NotificationCenter 투명 오버레이

macOS 데스크탑 위젯이 전체화면 투명 창 생성. computer-use 클릭 무효. 해결: `Cmd+Option+H` 로 다른 앱 숨기기.

### K-3. macOS keystroke 한글 입력 깨짐

AppleScript keystroke 가 한글 조합 입력 지원 안 함. 해결: AX API 의 `set value` 만 정상 동작.

### K-4. 서브에이전트 거짓 성공 (외부 도구 호출)

서브에이전트가 "Message sent" 보고했으나 실제 미전송. 해결: 메인 프로세스 직접 수행 + 전송 후 검증 (`kmsg read --limit 1 --json` 같은).

---

## L. Cross-bot SoP

### L-1. Lead 단계 진입 cross-check 명시 의무

Lead (오케스트레이터·하위 봇) 가 다음 단계 진입 시 직전 산출 cross-check 결과 명시 의무. 검증 게이트 cross-check 누락 → 다음 단계 silent 진입 회귀 패턴.

### L-2. 회의 primary + secondary DA cross-check 의무

회의 verdict 합성 시 primary DA (Codex/Gemini 외부) + secondary DA (Sonnet/Opus 내부) cross-check 의무. 단일 DA 회귀 risk 차단.

---

## 사용 패턴

### 패턴 1 — 새 회귀 발견

1. 본 문서의 카테고리 확인 → 매핑되는 cat 있으면 추가 케이스로 등재
2. 매핑 안 되면 새 카테고리 (M~) 신설
3. vault `shared/feedback_<topic>.md` 에 영구 등재
4. UserPromptSubmit hook 의 self-check 표에 1줄 추가

### 패턴 2 — 회귀 예방

세션 시작 시 본 문서 (또는 카테고리별 short ref) 자동 주입. UserPromptSubmit hook 의 4-gate 표가 procedural reminder.

## 관련 자원

- vault `<vault>/.claude-memory/shared/SHARED-INDEX.md` (24+ 카테고리 인덱스)
- vault `<vault>/agent-korea-daily/디버깅.md` (#1~#85 누적 케이스 DB, AK-Tofu 파이프라인 specific)
- skill: [../skills/bootstrap/SKILL.md](../skills/bootstrap/SKILL.md)
- self-check 표: [../skills/bootstrap/references/REFERENCE.md] (예정)
