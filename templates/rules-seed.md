<!-- rules-seed v1.2.0 -->
# Rules Seed — copy-once bot defaults

> 본 파일은 봇 생성 시(`create-bot`/`create-discord-bot` — Slack 은 `create-slack-bot`/`slack-configure`
> 가 같은 단계를 수행) 봇 작업 디렉토리(WD)에 **한 번만** 복사된다 (같은 디렉토리의 `CLAUDE.md` 가
> 이 파일을 가리키는 1줄을 갖는다 — `create-bot` Step 6). 이후 실행에서는 **절대 덮어쓰지 않는다**:
> 파일이 이미 있으면 그 사본을 직접 편집한다. 제품 동봉본이 이 파일보다 새 버전이면 봇 세션
> 시작 시점(SessionStart hook — `hooks/bot-session-init.sh`)에
> `[thiscode][WARN] rules-seed vX -> vY available — update by explicit command only`
> 한 줄이 뜰 수 있다 — 이 경고는 **자동 병합·자동 갱신을 하지 않는다**. 반영은 운영자 또는
> 봇에 대한 명시적 지시로만 한다.

## Rule 0 — Discord 인바운드에는 답장 도구로만 응답한다

Discord 에서 온 요청에는 **답장(reply) 도구로 보내야** 사용자에게 도달한다. 터미널에 찍은
출력은 사용자 화면에 **도달하지 않는다** — 봇은 답한 줄 알고 사용자는 못 받는 상태가 된다.
「답을 만들었다」와 「답을 보냈다」는 다른 일이고, 이 규칙이 요구하는 것은 뒤쪽이다.

한 턴에 답장 도구를 한 번도 쓰지 않은 채 끝내려 하면 `hooks/reply-gate.sh`(Stop 훅)가
막는다. Discord 턴이 아니면 그대로 통과한다.

## Rule 1 — DM(1:1) 답장 스레드 echo 금지 (Slack DM 한정)

Slack DM(1:1) 대화에서는 인바운드 메시지의 스레드 식별자(`thread_ts`)를 응답에 그대로
되돌려(echo) 스레드 마커로 쓰지 않는다. 인바운드 메시지 자체가 실제로 그 식별자를 실었을
때만 echo한다. 채널(비-DM) 응답의 기본 스레드 동작은 그대로 유지되며 브리지가 관리한다 —
이 규칙의 대상이 아니다.

(Discord DM 에는 이 개념이 적용되지 않는다 — Discord 는 채널 자체 Thread 객체로 스레드를
별도 관리하며 `thread_ts` 개념이 없다. **이 규칙은 Slack 브리지 한정.**)

## Rule 2 — 위키 저장 정책

이 봇에 옵시디언 위키(vault) 경로가 연결돼 있으면(봇 WD 의 `CLAUDE.md` "위키 연결" 절 ·
env `THISCODE_WIKI_PATH` 참조), 채팅 지시로 만든 Markdown 산출물은 그 위키 경로에 저장한다.
저장 후 응답에 저장 경로를 함께 명시한다 — 말없이 저장하지 않는다.

## Rule 3 — 본문 채널 봇 발주 금지 (회의실 게이트)

봇이 다른 봇에게 작업을 위임(발주·검수·구현·테스트 지시 등)할 때는 **top-level 공용
채널 본문에서 하지 않는다** — 전용 스레드를 만들고, 회의 기록 폴더(4-file:
00-context/01-spec/02-progress/03-outcome)를 먼저 만든 뒤 그 스레드 안에서만 진행한다.
단발 공지·생존 확인 핑은 본문에 보내되 `[공지]`/`[단발]`/`[핑]` 태그를 명기한다.
사람 대상 메시지에는 봇 멘션을 넣지 않는다.

설치가 구성되면 이 규칙은 `hooks/dispatch-room-gate.py`(PreToolUse deny 훅 +
`<state>/dispatch-gate.json` 설정)가 기계적으로도 막는다 — 규칙 텍스트와 훅은 같은
판정 기준을 공유하며, 훅 미설정 환경에서도 규칙 자체는 유효하다.
