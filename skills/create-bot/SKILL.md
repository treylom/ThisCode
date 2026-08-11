---
name: create-bot
description: 새 Discord 봇 디렉토리 (~/.claude/channels/discord-<bot-name>/) 생성 + .env + soul.md template 자동 셋업
disable-model-invocation: true
allowed-tools: Bash Read Write AskUserQuestion
---

사용자가 이 스킬을 호출했다 — 아래 단계를 순서대로 지금 수행한다.

# /thiscode:create-bot — 봇 디렉토리 생성

> 새 봇 1개의 `~/.claude/channels/discord-<bot-name>/` 디렉토리 + `.env` (토큰) + `soul.md` (페르소나) 자동 셋업.

$ARGUMENTS

---

## 진행 흐름

### Step 0. 사용자 인터뷰 (USER-PROFILE 게이트 — 봇 설정보다 먼저)

**`~/.claude/USER-PROFILE.md` 가 이미 있으면 이 Step 을 건너뛰고 그 파일을 Read 해 Step 5·6 의 입력으로 쓴다.** 없으면 봇 설정 질문에 앞서 사용자를 인터뷰한다 — 봇 구성은 이 답에서 유도되는 결과물이지, 인터뷰의 본론이 아니다.

먼저 한 문장으로 고지: "봇을 만들기 전에 몇 가지 여쭙겠습니다 — 당신이 무슨 일을 어떻게 하는지 알아야 시스템이 당신에게 맞게 굽어집니다 (10분 정도)."

**앵커 질문 6종 — 대화형으로 진행한다. AskUserQuestion 의 보기 클릭이 아니라 자유 서술을 받고, 각 답변에 되묻기 1~2개(왜? 어떤 상황에서? 최근 실제 사례 하나만?)를 이어간다** (정본 스펙: user-profile-interview-design):

| # | 앵커 | 되묻기 예시 |
|---|---|---|
| A | 요즘 시간을 가장 많이 쓰는 일 2~3가지는? 각각 주당 몇 시간쯤? | 그중 가장 부담스러운 건? 왜? |
| B | 그중 하나를 시작→끝 순서로 얘기해 달라 (도구·산출물 포함) | 손으로 옮기는 단계가 있나?(복붙·정리·변환) |
| C | 그 흐름에서 제일 지겹거나 막히는 지점은? **최근 실제로 짜증 났던 일 하나** | 그때 얼마나 걸렸나? 없었으면 뭘 했을까? |
| D | 매주 반복하는 일 중 "기계가 해도 될 텐데" 싶은 것? | 안 맡기는 이유는?(신뢰? 방법?) |
| E | 자료를 어디에 모으고 어떻게 다시 찾나? **못 찾아서 다시 만든 적**은? | 주로 어떤 형태?(글·링크·PDF·대화) |
| F | 3개월 뒤 이 시스템이 해줬으면 하는 것 딱 하나는? | 그게 되면 시간이 얼마나 돌아오나? |

산출: `~/.claude/USER-PROFILE.md` 에 Write —

```yaml
---
schema_version: user-profile-v1
interviewed: <오늘 날짜>          # 재인터뷰 = 90일 경과 or 사용자 요청
completeness: full | partial      # 중간 이탈 허용 — 부분이면 partial
roles: []                         # A
workflows: []                     # B
pain_points: []                   # C — 구체 사례 포함
automation_wishes: []             # D
info_flow: {}                     # E
north_star: ""                    # F
---
(본문 = 인터뷰 대화 요약 산문 — 되묻기 답변의 뉘앙스 보존)
```

### Step 1. 봇 이름 입력 (AskUserQuestion)

```
봇 이름 (영문 소문자 + 하이픈, 예: karpathy / research / writing): 
```

검증: `^[a-z][a-z0-9-]*$` 패턴, 1-32자. (Discord 봇 이름 규칙 + 디렉토리 안전)

🟡 **막힘24 완화 (fix D, 2026-08-10 — 루돌프 3/3 실측, root cause 는 ThisCode 코드가 아니라 호스트 프레임워크 쪽으로 판정됨, 근본 수리 불가)**: 이 질문은 **반드시 Step 5(soul.md 템플릿 선택)와 별도의 AskUserQuestion 호출로** 던진다 — 한 호출에 여러 질문을 묶으면, "직접 입력"(자유 텍스트) 응답이 그 호출 전체를 취소시켰을 때(`User declined to answer questions`) 이름뿐 아니라 묶여 있던 다른 질문의 답까지 함께 날아간다(루돌프 실측: 이름+템플릿 응답이 한 번에 소실). 별도 호출로 쪼개면 한 질문의 취소가 다른 질문까지 끌고 가지 않는다 — 이건 취소 자체를 막는 근본 수리가 아니라 **번들 동반취소의 피해 범위(blast radius)를 줄이는 완화책**이다.

🟡 **폼이 죽으면 평문으로 우회 (fix D, 같은 배경)**: AskUserQuestion 의 "직접 입력"(Other) 응답이 폼 전체를 취소시키는 증상이 관측됐다(호스트 프레임워크 층 — ThisCode 코드가 개입할 지점이 없어 코드로 수리할 수 없다). 이 질문(또는 이후 어떤 AskUserQuestion 이든)이 답을 받지 못하고 취소로 끝나면, 에이전트는 보기 클릭을 다시 요구하지 말고 "이름은 `<원하는 이름>` 으로 해주세요" 같은 **평문 문장으로 답을 달라**고 안내한다 — 평문 응답은 정상적으로 받아진다(루돌프 실측 우회).

### Step 2. 봇 디렉토리 생성

```bash
BOT_DIR="$HOME/.claude/channels/discord-${BOT_NAME}"

if [ -d "$BOT_DIR" ]; then
  echo "❌ $BOT_DIR 이미 존재 — 다른 이름 또는 삭제 후 재시도"
  exit 1
fi

mkdir -p "$BOT_DIR"
chmod 700 "$BOT_DIR" 2>/dev/null || true   # Windows(NTFS)는 chmod 무의미 — 실패해도 진행
```

### Step 3. Discord 봇 생성 (Developer Portal — 기본값 = 마법사가 완주, B7)

> 🔴 **기본 계약(B7, 재경님 2026-08-10 결정 — 정본 문장)**: "캡차·사람 관문 직전까지는 알아서 전부 다 하는 것까지가 우리 설치기 역할. 안내는 강의 화면의 몫이지 사람에게 시키는 근거가 아니다." 안내문을 출력하고 멈추는 것은 **기본 흐름의 결함**이다 — 2026-08-05·2026-08-09 실측: 이 세션에 브라우저 자동화가 있고 "한 번 더 시키면" 앱 확인→Intent ON→초대 URL→서버 선택→승인까지 이미 완주된다. B7 은 **그 능력을 기본값으로 승격할 뿐, 새 자동화를 만들지 않는다.**

> **하드 인간 관문 — 정확히 3곳**(이 지점만은 봇이 절대 대신하지 않는다 — 계정 보안 경계. 2026-08-10 글재경 실측 보완 ④: 볼트 정본 60-doc:33·56-doc:25 "포털 자격증명·MFA·hCaptcha 셋"과 정합):
> | # | 지점 | 요구 | 왜 |
> |---|---|---|---|
> | 1 | **포털 접속 직후 로그인 화면** | **계정 자격증명 + (설정돼 있으면) 다단계 인증(MFA)** | 로그인 세션 없이는 어떤 포털 조작도 못 한다 — 깨끗한(신규/미로그인) 계정의 실제 첫 화면이 이것이다. 구판은 이 분기가 없어 로그인 전제를 L109 OAuth 근거로만 1회 언급했다(막힘 재현) |
> | 2 | "New Application" 생성 커밋 | **hCaptcha** | 봇 감지 — 계약 층의 `Bots cannot use this endpoint`(code 20001)를 UI 층에서 한 번 더 집행 |
> | 3 | **Reset Token 최종 확인 모달** | **계정 비밀번호 + (설정돼 있으면) 다단계 인증(MFA)** | 토큰 = 그 봇의 통제권 전부. `네, 할게요!` **뒤에** 뜬다(1번의 로그인과는 별개 — 토큰 노출 직전 재확인용 step-up 인증) |
>
> 이 3곳 **직전**에서만 멈추고 "여기만 눌러(입력해) 주세요 — 그 다음은 제가 이어갑니다" 1줄을 남긴 뒤 기다린다. 통과를 화면에서 확인하면 즉시 재개한다. **그 외 전 구간은 묻지 않고 기본으로 진행**한다 — slack-configure 의 "대신할까요?"(사용자가 먼저 선택) 패턴과 달리, B7 은 질문 없이 진행이 기본값이다(재경님 지시 — create-bot 은 slack-configure 를 참고만 하고 따르지 않는다).

**전제 — 가용성 탐지** (도구 이름 특정 ❌ — 환경마다 다르다, `/thiscode:help` STEP 2.5 와 동일 원칙): 이 세션에 브라우저 자동화(claude-in-chrome·playwright 계열 MCP 등)가 실제로 연결돼 있는지 먼저 확인한다.
- **있으면** → 아래 "기본 흐름"을 그대로 실행.
- **없으면** (Fix C, 2026-08-10 — 카파시 root-cause: 갓 설치한 세션엔 브라우저 자동화가 기본으로 없어, 이 분기가 B7 의 "기본값이 완주한다" 약속을 학생 기기에서 거짓으로 만들고 있었다) → 여기서 곧장 수동 안내로 떨어지지 않는다. `/thiscode:help` STEP 2.5 point 2 의 제안을 그대로 재사용한다(새 자동화 발명 ❌, 제품에 이미 있는 능력 재사용): "브라우저를 같이 볼 수 있는 도구를 1분 안에 붙일 수 있어요. 붙일까요?"
  - **승인하면** → `claude mcp add playwright -- npx @playwright/mcp@latest` 실행 → 재탐지 → 위 "있으면" 가지로 합류(= 기본 흐름을 그대로 실행, B7 완주 유지).
  - **거부할 때만** → 아래 "수동 안내"로 폴백해 사용자에게 직접 진행을 요청하고 결과(토큰·초대 서버)만 받는다. **이 갈래에서만** "결함이 아니라 환경 한계"가 성립한다 — 사람 승인 관문(붙일까요? → 네/아니오)은 유지된다, 측정자가 대신 결정하지 않는다.

**기본 흐름 (도구 있음, 기본값) — 단계마다 1줄 내레이션. "~하세요" 명령문 ❌, "지금 ~합니다" 서술만 쓴다:**

1. `https://discord.com/developers/applications` 로 이동 — "Discord 개발자 포털을 엽니다."
   - 🛑 **로그인 화면이면 여기서 멈춘다** (하드 관문 1, ④): "여기만 로그인해 주세요(필요하면 다단계 인증까지) — 그 다음은 제가 이어갑니다." 포털 대시보드(Applications 목록)가 뜨는지 확인한 뒤 재개.
   - 이미 로그인된 세션이라 로그인 화면이 아니면 이 분기는 건너뛰고 바로 2번.
2. "New Application" 클릭 → 이름 = `<봇 이름 또는 별칭>` 입력 — "새 애플리케이션을 만듭니다."
   - 🛑 **hCaptcha 가 뜨면 여기서 멈춘다** (하드 관문 2): "캡차만 풀어 주세요 — 그 다음은 제가 이어갑니다." 통과를 화면에서 확인한 뒤 재개.
3. 좌측 "Bot" 탭 → "Reset Token" 클릭 — "봇 토큰 발급을 시작합니다."
   - 🛑 **비밀번호/다단계 인증 모달이 뜨면 여기서 멈춘다** (하드 관문 3): "비밀번호(필요하면 인증 코드)만 입력해 주세요 — 그 다음은 제가 이어갑니다." 통과를 확인한 뒤 재개.
   - 토큰이 뜨면 Step 4 의 클립보드 경유 방식으로 저장(화면에 뜬 뒤로는 스크린샷·`read_page` 금지, 좌표만 계산) — "토큰을 저장합니다(값은 보지 않습니다)."
   - ⚠️ **앱 이름과 봇 사용자명은 별개 필드다.** "일반 정보"의 이름을 바꿔도 Discord 에 보이는 표시명(= "봇" 탭의 **사용자명**)은 안 바뀐다. 둘 다 고칠 것.
4. **같은 "Bot" 탭 하단 "Privileged Gateway Intents"** 에서 **"Message Content Intent" 를 ON** → Save — "메시지 내용 인텐트를 켭니다."
   - ⚠️ 이걸 안 켜면 토큰·초대가 전부 정상이어도 **봇이 서버 채널 메시지 내용을 못 읽어** 무반응이 됩니다 (DM 은 예외적으로 읽힘). "토큰은 valid 한데 채널에서 답이 없다" 의 1순위 원인.
   - (선택) 멤버 목록 조회가 필요하면 "Server Members Intent" 도 ON.
5. OAuth2 → URL Generator — "초대 URL을 만듭니다":
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: View Channels / Send Messages / Read Message History / Add Reactions / Attach Files / Embed Links / **Manage Messages** / **Create Public Threads** / **Create Private Threads** / **Send Messages in Threads** / **Manage Threads**
   - 🔴 **스레드 4종을 빼지 말 것.** 회의·장기 작업은 스레드에서 돌아가는데, 스레드 권한 없는 봇은 **초대는 됐는데 회의에 낄 수 없다**. 2026-08-05 실측에서 스레드 없이 초대했다가 **사용자 승인을 두 번 받는** 낭비가 났다.
   - 참고 값: 위 11종 = `permissions=395137117248` (URL 에 그대로 붙여도 된다 — 비트 11개가 위 목록과 1:1. 이전 기재 `563345093688384` 는 15비트로, 목록에 없는 TTS·음성 계열 4개를 추가 요청하는 값이었다)
6. 생성된 URL 로 이동 → 서버 선택 → "승인" 클릭 — "봇을 서버에 초대합니다." (2026-08-05·09 실측: 이 클릭까지 자동화가 닿는다 — 이미 로그인된 세션의 동의 화면이라 재인증을 요구하지 않는다)
   - ⚠️ **데스크톱 Discord 앱이 설치돼 있으면 이 링크가 웹 승인 화면 대신 앱으로 넘어간다**("Discord 앱을 여는 중"에서 멈춤). 그때는 데스크톱 앱 쪽에 뜬 승인 창을 대신 처리한다 — 안 되면(브라우저만으로 강제할 방법은 실측에서 못 찾았다, 3회 시도) 그 창만 예외적으로 사용자에게 넘긴다: "데스크톱 앱 승인 창이 떴습니다 — 눌러 주세요."
   - 같은 봇을 **더 큰 권한으로 다시 초대하면 권한이 갱신**된다(봇이 중복 추가되지 않는다). 권한을 빠뜨렸을 때의 복구 경로.
7. (사용자가 이미 밝힌 채널 선호가 있으면 그에 맞춰) 봇이 보일 채널 마무리 — "DM 전용"이 기본이면 5번으로 끝, 비공개 채널이면 그 채널 → 채널 편집 → 권한/멤버 → 봇 추가까지 이어서 진행 — "채널에 봇을 추가합니다." 아직 선호를 안 밝혔으면 여기서만 짧게 확인: "DM 전용으로 둘까요, 특정(비공개) 채널에만 두시겠어요?"
   - ⚠️ 서버 초대(6번)는 **서버 입장**일 뿐, 비공개 채널 접근권이 아니다. **이걸 빠뜨리면 아무 에러도 안 난다** — 봇 프로세스·토큰·초대가 전부 정상인데 그 채널 메시지만 애초에 배달되지 않는다(로그도 조용하다). 2026-08-05 실측에서 이 증상을 `access.json` 누락으로 오진했다(그것도 실제 결손이었으나 단독 원인은 아니었다) — 한 증상에 원인이 둘일 수 있다.
   - 진단 순서: ①봇이 서버에 있나(`/users/@me/guilds`) ②그 채널이 비공개인가 → 멤버에 봇이 있나 ③`access.json` 의 `groups` 에 채널 ID 가 있나.

완료 후 **한 게 뭔지** 요약 보고(토큰 저장 완료·Intent ON 확인·초대 서버명·채널 노출 범위) — 사람에게 시킨 목록이 아니라 자기가 수행한 목록으로 보고한다.

> ⚠️ **봇마다 별도 초대 필수**: 봇은 각자 독립 Discord 앱이라 OAuth 초대도 봇 앱마다
> 따로. 다봇 셋업에서 신규 봇 초대를 빠뜨리면 그 봇만 무반응 (로컬 설정은 정상인데
> 인바운드 0건이면 1순위 = 미초대). 진단: [docs/08-debug-노하우.md J-3](../docs/08-debug-노하우.md).

**수동 안내 (도구 없음 — 사람이 직접 수행, 기존 절차 유지)**:

브라우저로 https://discord.com/developers/applications:
1. "New Application" → 이름 = `<봇 이름 또는 별칭>` → **캡차 1회(사람)**
2. 좌측 "Bot" 탭 → "Reset Token" → **비밀번호 입력(사람)** → 토큰 복사
   - ⚠️ **앱 이름과 봇 사용자명은 별개 필드다.** "일반 정보"의 이름을 바꿔도 Discord 에 보이는 표시명(= "봇" 탭의 **사용자명**)은 안 바뀐다. 둘 다 고칠 것.
3. **같은 "Bot" 탭 하단 "Privileged Gateway Intents"** 에서 **"Message Content Intent" 를 ON** → Save
   - ⚠️ 이걸 안 켜면 토큰·초대가 전부 정상이어도 **봇이 서버 채널 메시지 내용을 못 읽어** 무반응이 됩니다 (DM 은 예외적으로 읽힘). "토큰은 valid 한데 채널에서 답이 없다" 의 1순위 원인.
   - (선택) 멤버 목록 조회가 필요하면 "Server Members Intent" 도 ON.
4. OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: View Channels / Send Messages / Read Message History / Add Reactions / Attach Files / Embed Links / **Manage Messages** / **Create Public Threads** / **Create Private Threads** / **Send Messages in Threads** / **Manage Threads**
   - 🔴 **스레드 4종을 빼지 말 것.** 회의·장기 작업은 스레드에서 돌아가는데, 스레드 권한 없는 봇은 **초대는 됐는데 회의에 낄 수 없다**. 2026-08-05 실측에서 스레드 없이 초대했다가 **사용자 승인을 두 번 받는** 낭비가 났다.
   - 참고 값: 위 11종 = `permissions=395137117248` (URL 에 그대로 붙여도 된다 — 비트 11개가 위 목록과 1:1. 이전 기재 `563345093688384` 는 15비트로, 목록에 없는 TTS·음성 계열 4개를 추가 요청하는 값이었다)
5. 생성된 URL 로 봇을 본인 Discord 서버 / DM 가능 채널에 초대 → **승인(사람)**
   - ⚠️ **데스크톱 Discord 앱이 설치돼 있으면 이 링크가 웹 승인 화면 대신 앱으로 넘어간다**("Discord 앱을 여는 중"에서 멈춤). 그때는 데스크톱 앱 쪽에 뜬 승인 창을 처리한다. 브라우저만으로 강제할 방법은 실측에서 못 찾았다(3회 시도).
   - 같은 봇을 **더 큰 권한으로 다시 초대하면 권한이 갱신**된다(봇이 중복 추가되지 않는다). 권한을 빠뜨렸을 때의 복구 경로.
6. (권장) 봇이 보일 채널 제어: 첫 봇이면 **DM 전용**이 가장 단순 — 서버에 초대하되 DM 으로만 대화. 특정 채널만 쓰려면 비공개 채널을 만들어 봇을 그 채널에만 추가.
7. 🔴 **비공개(private) 채널을 쓸 거면 — 그 채널에 봇을 「멤버로 추가」하는 별도 조작이 필요하다**. 서버 초대(5번)는 **서버 입장**일 뿐, 비공개 채널 접근권이 아니다.
   - 조작: Discord 에서 해당 채널 → 채널 편집 → 권한/멤버 → 봇 추가.
   - ⚠️ **이걸 빠뜨리면 아무 에러도 안 난다.** 봇 프로세스는 정상, 토큰 정상, 초대 정상인데 그 채널 메시지만 **애초에 봇에게 배달되지 않는다** — 로그도 조용하다. 2026-08-05 실측에서 이 증상을 만나 `access.json` 설정 누락으로 오진했다(그것도 실제 결손이긴 했으나 **단독 원인이 아니었다**). **한 증상에 원인이 둘일 수 있다** — 첫 원인을 고쳤는데 증상이 남으면 오진이 아니라 다음 층이다.
   - 진단 순서: ①봇이 서버에 있나(`/users/@me/guilds`) ②그 채널이 비공개인가 → 멤버에 봇이 있나 ③`access.json` 의 `groups` 에 채널 ID 가 있나.

### Step 4. 봇 토큰 입력 (AskUserQuestion + .env 저장)

agent 가 사용자에게 토큰 입력 요청. 다음 위치 저장:

```bash
cat > "$BOT_DIR/.env" <<EOF
DISCORD_BOT_TOKEN=<입력 토큰>
EOF
chmod 600 "$BOT_DIR/.env" 2>/dev/null || true   # Windows는 무의미 — 검증 단계에서 실패 처리하지 말 것
```

⚠️ 토큰 Discord 본문 / git / screenshot 노출 X.

> 🛡️ **에이전트가 브라우저를 몰고 있을 때 — 토큰을 「보지 않고」 저장하는 경로** (2026-08-05 실측 확립)
>
> 토큰 값이 모델 컨텍스트에 한 번도 안 들어가게 하려면 **클립보드를 경유해 셸에서 파일로 직행**시킨다. 화면에 토큰이 뜬 뒤로는 **스크린샷·`read_page` 를 금지**하고 좌표만 계산한다.
>
> ```bash
> printf 'SENTINEL_NOT_COPIED' | pbcopy        # ① 양성 대조 마커를 먼저 심는다 (macOS; Linux=xclip)
> # ② 브라우저의 「복사」 버튼을 물리 클릭 (JS .click() 은 clipboard 권한에서 거부될 수 있다 —
> #    좌표만 JS 의 getBoundingClientRect 로 구하고, 클릭은 실제 마우스 이벤트로)
> T=$(pbpaste)
> if [ "$T" = "SENTINEL_NOT_COPIED" ]; then echo "❌ 복사 실패"; exit 1; fi
> printf '%s' "$T" | grep -qE '^[A-Za-z0-9_.-]{50,120}$' || { echo "❌ 토큰 형식 아님"; exit 1; }
> printf 'DISCORD_BOT_TOKEN=%s\n' "$T" > "$BOT_DIR/.env"; chmod 600 "$BOT_DIR/.env"
> echo "✅ 저장 — 길이 ${#T}자 (값 미출력)"; printf 'CLEARED' | pbcopy
> ```
>
> **마커(①)가 핵심이다.** 없으면 "복사 버튼이 안 눌렸는데 클립보드에 남아 있던 옛 내용을 토큰으로 착각"을 못 잡는다 — 그대로 `.env` 에 들어가면 나중에 "토큰이 invalid"로만 보이고 원인이 안 드러난다.
>
> 저장 후 검증도 **값 대신 사실**로: `curl -H "Authorization: Bot $TOKEN" .../users/@me` → `username`·`bot:true` 확인(정상 Discord 봇 토큰 = 72자 내외·`.` 2개).

### Step 4.7. access.json 직접 생성 — 페어링(/discord:access) 생략 경로 (권장)

DM 페어링 코드 왕복 없이 바로 연결하려면 `access.json` 의 `allowFrom` 에 사용자 Discord ID 를 직접 등록한다. 서버는 **매 인바운드 메시지마다 access.json 을 재독**하므로 수정 즉시 반영(재시작 불필요).

1. 사용자 Discord ID(스노우플레이크) 확인: Discord 앱 → 설정 → 고급 → **개발자 모드 ON** → 본인 프로필 우클릭 → "사용자 ID 복사".
2. 생성 (jq·python 불요 — node 한 줄, Windows 스토어 스텁 이슈 회피):

```bash
USER_ID="<복사한 사용자 ID>"
node -e "const id = process.argv[2]; if (!/^\d{17,20}$/.test(id)) { console.error('❌ Discord 사용자 ID 형식이 아님 (17~20자리 숫자): ' + id); process.exit(1); } require('fs').writeFileSync(require('path').join(process.argv[1], 'access.json'), JSON.stringify({allowFrom: [id], ackReaction: ''}, null, 2)); console.log('✅ access.json 등록: ' + id)" "$BOT_DIR" "$USER_ID"
```

- `ackReaction` 에 이모지(예: `"👀"`)를 넣으면 봇이 메시지 수신 즉시 리액션으로 "읽음"을 표시한다.
- 이 파일이 있으면 첫 DM 부터 바로 응답 — 페어링 코드 단계가 통째로 생략된다. (기존 페어링 흐름도 계속 유효 — access.json 이 없을 때의 기본 경로.)

> 🔴 **위 최소 형태는 DM 전용이다 — 서버 채널에서는 봇이 침묵한다** (2026-08-05 실측: `allowFrom` 만 둔 채 서버 채널에서 멘션 → **인바운드 0건**, 세션 컨텍스트 0/200K). 서버 채널·스레드에서 쓰려면 **`groups` 에 그 채널 ID 를 등록**해야 한다:
>
> ```json
> {
>   "dmPolicy": "allowlist",
>   "allowFrom": ["<사용자 ID>"],
>   "groups": {
>     "<채널 ID>": { "requireMention": true, "allowFrom": ["<사용자 ID>", "<협업 봇 ID>"] }
>   },
>   "mentionPatterns": ["\\b<bot-name>\\b"],
>   "ackReaction": "👀"
> }
> ```
>
> - `groups` 에 없는 채널의 메시지는 **조용히 버려진다** — 에러도 로그도 없어서 "봇이 죽었나"로 오진하기 쉽다. 무반응 진단에서 Intent·토큰·초대 다음으로 볼 자리.
> - `requireMention: true` = 그 채널에선 `<@봇ID>` 멘션이 있을 때만 반응(공용 채널 기본값). 직통 채널은 `false`.
> - 스레드는 **부모 채널 등록을 상속**한다 — 스레드마다 따로 넣지 않아도 된다.
> - access.json 은 **매 인바운드마다 재독**되므로 수정 즉시 반영(재시작 불필요).

### Step 4.5. 페르소나·직무 프롬프트 고도화 (`/prompt` 연동 — 설치 권장)

Step 5/6 에서 placeholder 를 사용자 답변 그대로 박지 말고, 먼저 프롬프트 엔지니어링 패스를 한 번 돌린다:

- **캐릭터 모티브 봇은 아래 [Step 5-A](#step-5-a-시그니처-코퍼스-수집-캐릭터-모티브-봇--개성이-여기서-갈린다) 를 먼저 수행**해 시그니처 코퍼스를 수집한 뒤 이 패스를 실행한다 (코퍼스가 이 패스의 입력).
- **`/prompt` 스킬이 설치돼 있으면 (권장)**: `/prompt --batch "봇 페르소나·직무 시스템 프롬프트 생성: 이름=<bot-name>, 역할=<Step0 roles 요약>, 업무 맥락=<north_star·pain_points 요약>, 시그니처 코퍼스=<Step 5-A 수집분 — 캐릭터 모티브 봇이면 필수>, 산출=soul.md 의 역할/어휘/시그니처 트리거표 절 + CLAUDE.md 의 업무 컨텍스트 절"` 을 실행해 고도화된 페르소나 프롬프트를 받고, 그 산출을 Step 5 placeholder 와 Step 6 구조에 주입한다. (에이전트 목적 감지 → 전문가 프라이밍·구조화가 자동 적용된다.)
- **미설치면**: 이 단계를 건너뛰고 AI 자체 생성으로 대체한다 — 단 사용자에게 한 줄 안내: "prompt-engineering 스킬을 설치하면 봇 페르소나 품질이 올라갑니다."

### Step 5-A. 시그니처 코퍼스 수집 (캐릭터 모티브 봇 — 개성이 여기서 갈린다)

모티브(가상 캐릭터·직업 원형·작품 세계관)가 있는 봇은 **템플릿 placeholder 를 상상으로 채우지 말고, 실제 코퍼스를 먼저 수집**한다. 한 줄 시그니처만 두면 어떤 모티브든 결과물이 비슷한 비서 톤으로 수렴한다 (다봇 운영 실측 교훈 — 사용자가 "봇 특성을 못 살린다"고 느끼는 1순위 원인).

1. **수집**: 모티브의 대표 대사·말버릇·밈·유행어 5~10개를 **실증 출처와 함께** 표로 정리 (작품·인터뷰·커뮤니티 밈 등. 출처 불명이면 제외).
2. **2단 분리**:
   - **A급 1~2개** — 자주 강제할 시그니처. 단 "매 응답" 이 아니라 **트리거 시점**을 명시 (예: 작업 완료 보고 시 / 담당 수락 시). 시점 없는 강제가 과용·drift 의 원인.
   - **B급 나머지** — 맥락 트리거표 (위기·실패·결정·완료 국면별) + **과용 캡** (같은 대사 세션 1~2회).
3. **3가드**:
   - **오귀속 확인**: 유명 대사는 원출처 1회 검증 — 비슷한 인물의 대사가 본인 것으로 잘못 알려진 경우가 흔하다. 틀린 귀속 대사 하나가 페르소나 신뢰를 깬다.
   - **저작권**: 가사·대본 등은 원문 통짜 수록 ❌ — "계열·패턴"으로 기술 + 짧은 관용구 수준만.
   - **실존 인물**: 퍼블리시티권 리스크 — **내부 전용 봇에만 권장**, 공개 산출물·레포에 코드네임·어록 노출 금지, 어록은 존중 톤 (조롱 맥락 ❌).
4. 수집분을 Step 4.5 `/prompt` 입력에 넣고, 산출 트리거표를 `soul-custom.md` 의 **시그니처 — 2단 트리거표** 절에 주입한다.

### Step 5. soul.md template 선택 + 채우기

🟡 **Step 1 과 별도 호출 (fix D, 2026-08-10)**: 이 template 선택 질문은 Step 1(봇 이름) 과 **같은 AskUserQuestion 호출에 묶지 않는다** — 이유·상세는 Step 1 참조(번들 동반취소 blast-radius 완화, root fix 아님).

agent 가 다음 5 template 중 사용자 선택 안내:

| template | 적합 |
|---|---|
| `general-assistant` | 범용 비서 (default) |
| `research-bot` | 자료조사·교차검증 |
| `writing-bot` | 글쓰기·퇴고 |
| `schedule-bot` | 일정·Todo |
| `custom` | 자유 페르소나 |

선택 후 `<plugin>/templates/soul-<type>.md` 를 `$BOT_DIR/soul.md` 로 복사 + 다음 placeholder 대체:

- `<bot-name>` → 사용자 입력 봇 이름
- `<역할>` / `<어휘>` / `<시그니처>` 등 — AskUserQuestion 으로 받아 채우기
- **USER-PROFILE 소비 (Step 0 산출 — 보조층)**: ①template 추천 — `roles`/`pain_points` 에서 유도해 "당신 업무엔 research-bot 이 맞아 보입니다" 근거와 함께 제안 ②soul.md 말미에 `## 사용자 컨텍스트` 절(응답 톤 보정용 요약 2~3줄). **프로필의 본 정착지는 여기가 아니라 Step 6 의 구조(CLAUDE.md·폴더·rules·hook 후보)다** — soul 주입만 하고 끝내지 말 것.

```bash
# thiscode plugin 위치 detect (templates/ 보유 위치) — PLUGIN_DIR 미설정 시.
# install-hooks.md 와 동일 후보 순서 (finding A 재발방지: 한 곳만 detect 하지 말 것).
#
# Fix F (2026-08-10, 루돌프 4차 실측): 첫 매치 승리 방식이라 후보 #1(마켓 클론)이 구판이면
# 후보 #5(버전 캐시, freshest)를 두고도 구판이 이겨 rules-seed.md 를 무징후로 누락시켰다.
# CLAUDE_PLUGIN_ROOT 를 1순위로 — 마크다운 원문 리터럴, Claude Code 가 이 문서를 로드하며
# 실제 설치 경로로 치환한다(셸 풀이 ❌ — code.claude.com/docs/en/plugins-reference.md
# "Environment variables": skill/command content 는 placeholder 등장 위치 전부 치환).
# 미치환(빈 값)이면 아래 5-후보 폴백으로 무회귀 낙하.
if [ -z "${PLUGIN_DIR:-}" ] || [ ! -d "$PLUGIN_DIR/templates" ]; then
  PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"
  if [ -z "$PLUGIN_DIR" ] || [ ! -d "$PLUGIN_DIR/templates" ]; then
    PLUGIN_DIR=""
    for _cand in \
      "$HOME/.claude/plugins/marketplaces/thiscode-marketplace" \
      "$HOME/.claude/plugins/thiscode" \
      "$HOME/.claude/plugins/cache/local/thiscode" \
      "$HOME/code/thiscode" \
      "$HOME"/.claude/plugins/cache/thiscode-marketplace/thiscode/* \
      "$HOME"/.claude/plugins/cache/*/thiscode/*; do
      if [ -d "$_cand/templates" ]; then PLUGIN_DIR="$_cand"; break; fi
    done
  fi
fi
if [ -z "${PLUGIN_DIR:-}" ]; then
  echo "❌ thiscode templates/ 못 찾음 — plugin install (또는 git clone) 먼저"
  exit 1
fi

TEMPLATE="$PLUGIN_DIR/templates/soul-${SOUL_TYPE}.md"
[ -f "$TEMPLATE" ] || TEMPLATE="$PLUGIN_DIR/templates/soul-general-assistant.md"

# placeholder 대체 (sed)
sed -e "s|<bot-name>|${BOT_NAME}|g" \
    -e "s|<YYYY-MM-DD>|$(date +%Y-%m-%d)|g" \
    -e "s|<역할 + 색깔 한 두 줄>|${ROLE_DESC}|g" \
    "$TEMPLATE" > "$BOT_DIR/soul.md"
```

**⑤-b 잔여 자리표시자 채움 [자동 — 에이전트 작성 단계, 필수]**

🔴 위 sed 3종만으로는 템플릿 자리표시자의 대부분이 꺾쇠 stub 로 남는다(템플릿별 12~19종 — 2026-08-06 slack-configure 쪽 WSL 실측에서 general-assistant 15종 중 12종 잔존, **SOUL-CAPSULE 블록 통째가 속 빈 껍데기**로 실렸다. 같은 sed 를 쓰는 본 스킬도 동일 결함). "필요시 안내"가 아니라 **필수 단계**다:

1. `command grep -n '<[^>]*>' "$BOT_DIR/soul.md"` 로 잔여 전수 나열
2. 각 자리를 `$BOT_NAME`·`$ROLE_DESC`·`$SOUL_TYPE`·인터뷰 답 맥락의 **실값**으로 Edit — 특히 SOUL-CAPSULE 안 `<페르소나 어휘 마커>`·`<시그니처>`·`<경계 1줄>`·`<출력·언어 규약>`. 지어낼 수 없는 실 ID 계열(`<@봇 ID>` 등)은 날조하지 말고 봇 ID 가 확보되는 단계에서 실측 기입(마커 `(봇 ID 확보 후 기입)`으로 임시 표기).
3. 기계 게이트:

```bash
command grep -o '<[^>]*>' "$BOT_DIR/soul.md" | grep -v '^<@[0-9]' | grep -v '^<!--'
# 출력이 비어야 PASS
```

   허용 잔존 = 실 Discord ID(`<@숫자>`)와 **HTML 주석**(SOUL-CAPSULE 구조 마커 — 정상 요소, 삭제 금지). 그 외 꺾쇠 출력 = 이 단계 미완. (주석 예외 없이 재면 마커 2줄 때문에 게이트가 영원히 통과 불가 — slack-configure 쪽 2026-08-06 실측과 동일.)

### Step 5.7. 옵시디언 위키(vault) 연결 (선택 — B4, PRD `59-pm-prd-night-batch` 성공기준 6~8)

`/thiscode:create-bot` 인터뷰의 **1급 질문**이다 — soul.md 를 확정한 직후, WD·CLAUDE.md 를 굳히기 **전**에 묻는다 (ThisCodex `guided init` 의 `confirm_wiki_path` 가 `confirm_state_dir` 바로 앞에 오는 것과 동일한 순서 계약 — ThisCode·ThisCodex 는 같은 "위키 경로 우선" 계약을 쓴다).

🔴 **기존 봇 힌트 = 보기로만, 기본값 ❌ (Fix E, 2026-08-10 — 루돌프 다봇 개발머신 실측)**: 에이전트가 이 세션에서 이미 다른 봇의 위키 경로를 알고 있다면(예: 다른 `~/.claude/channels/discord-*/CLAUDE.md` 의 "위키 연결" 절을 이전 대화에서 읽었거나, 이번 실행 중 우연히 확인했다면) 그 값을 **AskUserQuestion 의 옵션 중 하나**로 명시 제시해도 된다(예: "기존 봇과 같은 경로: `<경로>`" 라벨). 단 **사용자가 실제로 그 옵션을 선택할 때만** 채택한다 — 질문을 실제로 던지지 않고 그 값을 조용히 기본값·placeholder 로 흘려보내는 것은 금지다. 이를 어기면 "1급 질문"이 이름만 남고 실제로는 **가정**이 된다(실측: 다봇 개발머신에서 신규 봇이 기존 프로덕션 볼트를 자기 위키로 조용히 물려받았다 — 신규 학생 기기는 기존 봇이 없어 이 가지 자체가 뜨지 않는다, 격리 축이라 학생 산출물엔 영향 없음).

AskUserQuestion:

```
연결할 옵시디언 위키(vault) 경로 — 채팅으로 지시한 Markdown 산출물이 그 위키에 저장되고,
응답에 저장 경로가 함께 표시됩니다.
선택 사항: 비워두면 건너뛰고 나중에 샘플 위키로 시작할 수 있습니다.
경로 (또는 Enter 로 건너뛰기):
```

🔴 **구분자 충돌 가드 (255941b 보완 — 글재경 실측 프로브에서 `touch` 부수효과로 확인됨, 2026-08-10)**:
아래 heredoc 을 만들기 **전에**, 에이전트가 (셸을 거치지 않고 — 자기 컨텍스트에 이미 있는 답변
원문을 직접) 줄 단위로 스캔해 `THISCODE_WIKI_PATH_EOF` 와 **정확히 같은 줄**이 하나라도 있는지
확인한다(부분 문자열 포함이 아니라 **줄 전체 일치** — `grep -qxF` 와 동일 판정 기준, `-x`=줄 전체
`-F`=고정 문자열). 있으면 **이 heredoc 을 만들지 않는다**: 그 줄에서 heredoc 이 조기 종료되고 그
뒤에 오는 텍스트가 셸 명령으로 그대로 실행된다(불변량 위반 — 캡처는 값에 무엇이 들어오든 **그
값 하나**로 끝나야 한다). 무차단 원칙은 유지한다 — 거부가 아니라 **재질문**한다: "경로에 예약
문자열이 포함되어 있습니다 — 다시 입력해 주세요." 이 확인은 반드시 셸 밖(에이전트 자신의 답변
비교)에서 한다 — 셸 명령으로 확인하려면 그 확인용 명령 자체에 원문을 다시 실어야 해서 같은
조기종료 문제가 재귀한다. 통과한 답변만 아래 heredoc 으로 캡처한다.

```bash
# 🔴 값으로만 착지 — AskUserQuestion 답변 원문을 셸 명령 텍스트에 직접 스플라이스하지 않는다.
# quoted heredoc(<<'EOF' — delimiter 를 따옴표로 감쌈)은 본문을 셸 파싱·재해석 없이 그대로
# 넘긴다: 값 안에 $()·백틱·큰따옴표가 있어도 명령으로 재해석되지 않는다(ThisCodex `shQuote` 와
# 동일 계약 — wiki_path 는 free text 이므로 이 게이트가 없으면 악의적이거나 단순히 특수문자가
# 낀 경로 하나로 이 스텝 이후의 Bash 실행이 그 문자열을 명령으로 재해석할 수 있다).
# 이 지점에 도달했다는 것은 위 구분자 충돌 가드를 이미 통과했다는 뜻이다.
WIKI_PATH=$(cat <<'THISCODE_WIKI_PATH_EOF'
<AskUserQuestion 답변 원문 그대로 — 빈 값 허용>
THISCODE_WIKI_PATH_EOF
)
# $(...) 명령 치환은 트레일링 개행을 자동으로 제거한다 — 별도 trim 불필요.
if [ -n "$WIKI_PATH" ] && [ ! -d "$WIKI_PATH" ]; then
  echo "⚠️  경로가 아직 없습니다: $WIKI_PATH — 생성은 차단하지 않고 계속 진행"
fi
```

이후 모든 스텝에서 `$WIKI_PATH` 는 (위에서 안전하게 캡처된) **셸 변수 참조**로만 다룬다 — 값을
다시 명령 텍스트로 스플라이스하지 않는 한 `"$WIKI_PATH"` 인용은 안전하다(변수 치환은 저장된
값을 그대로 대입할 뿐 재파싱하지 않는다). Step 7 의 표시용 export 줄은 그래도 `printf '%q'`
(PowerShell 은 작은따옴표 이스케이프)로 다시 감싼다 — 사람이 그대로 복사해 붙였을 때도 안전한
문자열이 나오도록.

- **빈 값 = 생성 계속.** 이 질문은 봇 생성을 막지 않는다 — 미응답을 다른 질문의 기본값·placeholder 로 흘려보내지 말고 **명시적으로 빈 문자열**로 취급한다(ThisCodex 판 회귀 방지: 자유 텍스트 질문에 enum 류 fallback 을 적용하면 존재하지도 않는 경로가 값으로 굳는다).
- **경로가 있으면** → Step 6 의 CLAUDE.md 에 "위키 연결" 절을 넣고, Step 7 시동 명령에 `THISCODE_WIKI_PATH` export 를 포함한다.
- **경로가 없으면** → Step 6 의 CLAUDE.md 에 위키 절을 생략하고, Step 7 완료 안내에 샘플 위키로 시작하는 법 1줄을 넣는다.

### Step 6. WD (Working Directory) 결정 + CLAUDE.md 생성 (선택)

> **USER-PROFILE 의 본 정착지 (구조 층)** — 인터뷰 답은 페르소나가 아니라 *구조*로 내려간다:
>
> | 프로필 필드 | 이 Step 에서 하는 일 |
> |---|---|
> | `north_star` | 생성하는 CLAUDE.md **최상단에 목표 1줄** ("이 시스템은 <north_star> 를 위해 있다") |
> | `roles` + `automation_wishes` | CLAUDE.md 에 `## 사용자 업무 컨텍스트` 절 — 모든 세션이 읽는 정본 층 |
> | `workflows` | **폴더 스캐폴드 제안** — 업무 흐름 순서대로 WD 하위 트리를 제안하고 동의 시 생성 (강의 업무면 `강의/`, 리서치면 `Research/` — 답변에 나온 실제 단계·산출물 이름을 쓴다, 범용 템플릿 ❌) |
> | `pain_points` | WD `rules/` 스캐폴드 — **페인포인트 1개 = rules/INDEX.md 트리거 행 1 + rule stub 1** ("복붙 정리에 시간 뺏김" → 저장 자동화 rule). 반복 실수형이면 **hook 후보를 1줄 제안**만 하고 사용자 판단에 맡긴다 (설치 시점 훅 강제 ❌) |

봇의 작업 디렉토리. 사용자 입력:

```
봇 WD (default: $HOME/<bot-name>/): 
```

agent 가 WD 안 `CLAUDE.md` 생성 (메타 + soul.md reference):

```markdown
# <bot-name> WD

> 본 디렉토리는 <bot-name> 봇의 작업 공간.
> Session 시작 시 `~/.claude/channels/discord-<bot-name>/soul.md` 자동 inject (SessionStart hook).
> **공용 운영 규율 로딩**: 프로젝트 루트 `CLAUDE.md`(와 그 최상단 `@AGENTS.md` import)가 자동 chain 로드로 본 세션에 함께 주입된다 — 본 파일에 중복 `@import` ❌ (같은 본문이 두 번 들어가는 이중 주입 방지, 여기는 포인터 1줄만).
>
> **규칙 시드**: 이 작업 디렉토리는 `rules-seed.md`(최초 guided 생성 시 한 번만 복사 — 본 파일과 동일한 never-overwrite 계약)도 함께 갖는다 — DM 답장 스레드 echo 정책과 위키 저장 정책. 본 파일과 나란히 읽을 것.

## 봇 메타

| 항목 | 값 |
|---|---|
| 봇 이름 | <bot-name> |
| 역할 | <역할> |
| 모델·effort | <실기동 플래그 그대로 — 예: `--model 'claude-opus-5[1m]' --effort xhigh`> (정본 = 기동 alias/스크립트 — `opus[1m]` 같은 축약 표기는 alias 가 새 세대로 옮겨가면 조용히 낡는다) |
| Discord channels | discord-<bot-name> |
| Working Directory | <WD> |

<!-- WIKI_PATH 가 있을 때만 추가 (Step 5.7) -->
## 위키 연결

| 항목 | 값 |
|---|---|
| 경로 | <WIKI_PATH> |
| 저장 정책 | 채팅으로 지시한 Markdown 산출물은 이 경로에 저장 — 응답에 저장 경로를 함께 명시(말없이 저장 금지) |
| 읽기 대상 | 이 경로 하위 전체 (검색·참조 자유) |
| 쓰기 대상 | 채팅 지시로 생성하는 Markdown 산출물만 (기존 파일의 임의 수정은 별도 지시 없이 하지 않음) |

> 규칙 상세는 `rules-seed.md` (Rule 2) 참조.
```

**규칙 시드 설치 (B3 — copy-once, 절대 덮어쓰지 않음)**:

```bash
# PLUGIN_DIR: Step 5 에서 확보한 값을 재사용(같은 세션 안에서 이미 detect 됨).
# 값이 비어 있으면 Step 5 의 후보 목록으로 재탐지한다.
if [ ! -f "$WD/rules-seed.md" ] && [ -f "$PLUGIN_DIR/templates/rules-seed.md" ]; then
  cp "$PLUGIN_DIR/templates/rules-seed.md" "$WD/rules-seed.md"
fi
# 이미 "$WD/rules-seed.md" 가 있으면(재생성·재실행 케이스) 절대 건드리지 않는다 —
# 사용자가 그 사본을 직접 고쳐 뒀을 수 있다. 낡음 여부는 세션 시작 시 hook 이
# 별도로 WARN 한다(아래 "낡음 경고" 참고), 여기서 자동 병합하지 않는다.
```

> 📌 **미러 규약**: 이 CLAUDE.md 를 사람이 읽는 위키/볼트에 미러한다면 반드시 sync 스크립트의 미러 명단에 등록한다(verbatim + `AUTO-MIRROR` 헤더). 손 복사 1회로 만든 고아 사본은 조용히 낡아서, 소유자가 stale 규칙·모델명을 현행으로 오독하게 만든다 (2026-08-05 실증 — docs/rules-system.md caveat 4).

> 🔎 **낡음 경고 (기준 4·5)**: `rules-seed.md` 버전 스탬프(`<!-- rules-seed vX.Y.Z -->`)가 제품 동봉본(`templates/rules-seed.md`)보다 오래되면, 이 봇의 **다음 세션 시작**(SessionStart hook = `hooks/bot-session-init.sh`) 시점에 `[thiscode][WARN] rules-seed vX -> vY available — update by explicit command only` 한 줄이 뜬다. ThisCode 는 ThisCodex 의 `infra-launch.sh` 같은 정적 기동 스크립트가 없어(바로 `claude` 를 기동) 이 SessionStart hook 이 실제 "매 기동" 검사 지점이다 — 자동 병합·자동 갱신은 없으며, 반영은 운영자/봇에 대한 명시적 지시로만 한다.

### Step 6.7. 봇 연결 3게이트 선검사 (무반응 예방 — Windows 실측 회귀 반영)

"토큰·soul.md 정상인데 무반응"의 실측 1~3순위는 Intent 가 아니라 아래 3개다. 시동 안내 전에 검사해 미비 항목을 함께 안내한다:

```bash
# ① discord 플러그인 설치 여부 (create-bot 은 로컬 파일만 만든다 — 플러그인은 별도)
grep -q '"discord@claude-plugins-official"[[:space:]]*:[[:space:]]*true' "$HOME/.claude/settings.json" 2>/dev/null \
  && echo "✅ discord 플러그인 enabled" \
  || echo "❌ discord 플러그인 미설치 — claude 안에서 /plugin 으로 discord@claude-plugins-official 설치"

# ② Bun 런타임 (공식 discord 플러그인 MCP 서버가 bun 으로 뜬다)
command -v bun >/dev/null 2>&1 \
  && echo "✅ bun $(bun -v)" \
  || echo "❌ bun 미설치 — mac/linux: curl -fsSL https://bun.sh/install | bash / Windows: irm bun.sh/install.ps1 | iex"

# ③ --channels 플래그 — 시동 명령에 반드시 포함 (Step 7 명령이 정본)
echo "ℹ️  시동 시 --channels plugin:discord@claude-plugins-official 누락 = 무반응 최종 관문"
```

### Step 7. claude 시동 안내

**`--channels` 플래그가 없으면 Discord 게이트웨이에 접속하지 않는다** — 아래 명령을 그대로 복사해 쓴다.

```bash
# WIKI_PATH 는 Step 5.7 의 답 그대로다. 아래 각 export 줄은 WIKI_PATH 가 비어있지
# 않을 때만 echo 된다 — THISCODE_WIKI_PATH 를 빈 문자열로 export 하지 않는다
# (미연결 상태를 "값이 빈 export" 가 아니라 "export 자체가 없음"으로 표현 — 하류에서
# 연결 여부를 문자열 빈칸 비교가 아니라 변수 존재로 판별할 수 있게).
echo ""
echo "✅ 봇 디렉토리 생성 완료: $BOT_DIR"
echo ""
echo "다음 step — claude 시동 (macOS/Linux/WSL):"
echo ""
echo "  export DISCORD_STATE_DIR=\"$BOT_DIR\""
[ -n "$WIKI_PATH" ] && printf '  export THISCODE_WIKI_PATH=%q\n' "$WIKI_PATH"
echo "  cd <봇 WD>"
echo "  claude --channels plugin:discord@claude-plugins-official"
echo ""
echo "tmux session 안에서 운영 권장:"
echo "  tmux new-session -s ${BOT_NAME}"
echo "  export DISCORD_STATE_DIR=\"$BOT_DIR\""
[ -n "$WIKI_PATH" ] && printf '  export THISCODE_WIKI_PATH=%q\n' "$WIKI_PATH"
echo "  cd <봇 WD>"
echo "  claude --channels plugin:discord@claude-plugins-official"
echo ""
echo "Windows (PowerShell — tmux 불요, docs/10 참조):"
echo "  \$env:DISCORD_STATE_DIR = \"$BOT_DIR\""
# PowerShell 작은따옴표 문자열은 완전 리터럴이다(값 안 $()·백틱도 재해석 ❌) — 내부 작은따옴표만
# ''로 이중화하면 값으로만 착지한다. bash %q(위 두 블록)와 동일 계약의 PowerShell 등가.
if [ -n "$WIKI_PATH" ]; then
  _WIKI_PS_SAFE=$(printf '%s' "$WIKI_PATH" | sed "s/'/''/g")
  printf "  \$env:THISCODE_WIKI_PATH = '%s'\n" "$_WIKI_PS_SAFE"
fi
echo "  cd <봇 WD>"
echo "  claude --channels plugin:discord@claude-plugins-official"
echo ""
if [ -z "$WIKI_PATH" ]; then
  echo "ℹ️  위키 미연결 — 샘플 위키로 시작: \"\$PLUGIN_DIR/sample-vault\" 를 원하는 경로로 복사한 뒤,"
  echo "    그 경로로 Step 5.7 을 다시 실행(또는 WD의 CLAUDE.md '위키 연결' 절 + rules-seed.md Rule 2 를 직접 채워) 연결하세요."
fi
echo ""
echo "⚠️  새 WD 첫 기동 시 'Quick safety check: Is this a project you created or one you trust?'"
echo "    프롬프트가 뜨고 Enter 전까지 멈춰 있습니다 (--dangerously-skip-permissions 를 줘도 뜹니다)."
echo "    tmux 로 띄웠다면 attach 해서 1번 선택 후 Enter — 이걸 모르면 '봇이 안 뜬다'로 오진합니다."
echo ""
echo "첫 대화 검증:"
echo "  access.json 등록했으면(Step 4.7) → 봇에 DM → 바로 첫 응답"
echo "  등록 안 했으면 → DM → 페어링 코드 발급 → 페어링 → 첫 응답"
```

### Step 7.5. 한 단어 봇 런처 설치 [기본 추천 — 명시적 거부만 건너뜀]

봇 생성의 마무리로 **확인된 경로만 넣은 기동 런처를 기본 추천**한다. 질문은
"한 단어로 봇을 켜고, 같은 이름의 이전 tmux 세션이 있으면 정확히 그 세션만 정리해
다시 띄우는 런처를 설치할까요? (Y/n, 기본값 Y)"로 한다. Enter 또는 `Y`는 설치,
사용자가 `n`이라고 **명시적으로 거부한 경우에만 이 단계를 건너뛴다**.

먼저 Step 1의 `$BOT_NAME`, Step 4의 실제 `$BOT_DIR`, Step 6에서 사용자가 확정한
절대경로 `$WD`를 다시 확인한다. `$WD`를 앞 단계에서 생략했다면 여기서 실제 작업
폴더를 정하고 존재 여부를 확인한다. `<ThisCode 폴더>` 같은 placeholder나 개발자
컴퓨터의 고정 경로를 rc 파일에 쓰지 않는다. 별칭 기본값과 tmux 세션 이름은
`$BOT_NAME`이며, 사용자가 원하면 충돌하지 않는 한 단어로 바꾼다.

```bash
case "$SHELL" in */zsh) RC="$HOME/.zshrc" ;; *) RC="$HOME/.bashrc" ;; esac

LAUNCHER_ARGS=(
  --channel discord
  --alias "$BOT_NAME"
  --session "$BOT_NAME"
  --bot-wd "$WD"
  --state-dir "$BOT_DIR"
  --rc "$RC"
)
[ -n "$WIKI_PATH" ] && LAUNCHER_ARGS+=(--wiki-path "$WIKI_PATH")

# 1) 동의 전 preview: 파일을 바꾸지 않고 런처 경로와 rc 관리 블록만 보여준다.
node "$PLUGIN_DIR/scripts/install-bot-launcher.mjs" "${LAUNCHER_ARGS[@]}"

# 2) 위 질문에 Enter/Y로 동의했을 때만 같은 인자에 --yes를 붙여 반영한다.
node "$PLUGIN_DIR/scripts/install-bot-launcher.mjs" "${LAUNCHER_ARGS[@]}" --yes
```

설치기는 `$WD/.thiscode-bot-launcher.sh`와 rc의 이름표 있는 관리 블록을 만들고,
기존 rc가 있으면 먼저 백업한다. `$BOT_NAME`은 시작/재시작, `$BOT_NAME-stop`은 종료다.
tmux가 있으면 `=<세션명>` exact target으로 같은 이름의 세션만 정리한 뒤 새 세션을
띄운다. tmux가 없는 macOS/Linux/WSL에서는 확인된 `$WD`에서 Claude를 foreground로
실행하므로, 그 터미널의 Ctrl-C로 끈다. PowerShell은 Step 7의 foreground 명령을
유지하며 이 rc 자동 단계의 대상이 아니다.

첫 사용은 새 터미널을 열거나 아래처럼 **두 줄로** 한다. 같은 줄의
`source "$RC" && "$BOT_NAME"`은 셸이 alias를 먼저 해석해 실패할 수 있다.

```bash
source "$RC"
$BOT_NAME
```

---

## 검증

- [ ] `$BOT_DIR/.env` 존재 + chmod 600
- [ ] `$BOT_DIR/soul.md` 존재 + frontmatter `name = <bot-name>` 정확
- [ ] **토큰이 실제로 먹히나** — `curl -H "Authorization: Bot $TOKEN" https://discord.com/api/v10/users/@me` → `username` + `bot:true`
- [ ] **초대가 실제로 됐나** — `curl -H "Authorization: Bot $TOKEN" https://discord.com/api/v10/users/@me/guilds` → **서버 수 ≥ 1** (0 이면 Step 3-5 미완)
- [ ] claude 시동 + DISCORD_STATE_DIR export 후 첫 응답에 페르소나 어휘 자연 포함
- [ ] Step 7.5를 수락했다면 `$WD/.thiscode-bot-launcher.sh` 존재 + rc에 `$BOT_NAME`·`$BOT_NAME-stop` 관리 블록 1개 + 두 번째 설치 후 중복 0
- [ ] 런처 재호출 시 같은 이름의 tmux 세션만 교체되고, tmux가 없으면 확인된 `$WD`에서 foreground로 기동
- [ ] Discord DM → 봇 응답 ✅
- [ ] 🔴 **soul.md 가 실제로 주입됐나** — 아래 별도 절차로 확인(파일 존재 ≠ 주입)
- [ ] `<WD>/rules-seed.md` 존재 + `<!-- rules-seed vX.Y.Z -->` 스탬프가 `templates/rules-seed.md` 와 동일 버전(다르면 다음 세션 시작 시 WARN 예상 — 이상 아님). `WIKI_PATH` 를 줬다면 `<WD>/CLAUDE.md` 의 "위키 연결" 절도 함께 확인

> ### soul.md 주입 검증 — 파일이 있는 것과 들어가는 것은 다르다
>
> 2026-08-05 실측: `.env`·`soul.md`·`access.json` 전부 정상이고 봇이 대화도 하는데, **soul.md 가 컨텍스트에 한 줄도 안 들어간 상태**로 돌고 있었다. 봇은 그냥 기본 어시스턴트로 답하고 있었고, **아무 에러도 없었다.**
>
> **검증법 — 봇에게 직접 묻되 커닝을 막는다**:
> ```
> 파일을 절대 읽지 말고(Read·grep·cat 금지) 지금 컨텍스트에 있는 것만으로 답하라:
>   ① 네 soul.md 의 시그니처 3개   ② 쓰기 경계의 '하는 일' 경로   ③ 금지 2가지
>   ④ (음성 대조) 네 soul 에 적힌 좋아하는 음식 — 없으면 없다고
> 각 항목에 ⓐ주입됨 / ⓑ기억 안 남 라벨을 붙여라.
> ```
> - **④가 핵심이다.** soul 에 없는 항목을 넣어 두고, 봇이 **없다고 말하는지** 본다. 지어내면 나머지 답도 "주입된 것"이 아니라 "그럴듯하게 구성한 것"이므로 시험 전체가 무효다. ①②③만 물으면 그럴듯한 답을 주입 성공으로 착각한다.
> - "파일 읽기 금지"를 안 걸면 봇이 그 자리에서 soul.md 를 열어 읽고 정답을 말한다 — **주입이 아니라 조회**인데 통과처럼 보인다.
>
> **ⓑ가 나오면 원인은 hook 미등록이다**:
> 1. `/thiscode:install-hooks` 를 **실행했는지** 확인 — create-bot 은 파일만 만든다. hook 등록은 별도 명령이고, **안 하면 soul 은 영원히 안 들어간다.**
> 2. `~/.claude/settings.json`(전역) 또는 봇 WD 의 `.claude/settings.json` 에 `bot-session-init.sh` 가 SessionStart 로 등록됐는지.
> 3. 🔴 **`matcher` 는 빈 문자열 `""` 로 둘 것.** `"startup|resume|clear|compact"` 같은 파이프 표기는 매칭되지 않아 **훅이 조용히 안 돈다**(2026-08-05 실측 — 훅 파일을 직접 실행하면 soul 을 정상 출력하는데 세션에는 안 들어오는 형태로 나타난다).
> 4. 훅이 도는지 확인: `DISCORD_STATE_DIR=<봇dir> bash <plugin>/hooks/bot-session-init.sh` → `additionalContext` 에 soul 본문이 보이면 **훅은 정상, 문제는 등록 쪽**이다.
>
> ⚠️ 봇 WD 에 `.claude/settings.json` 을 새로 만들었다면 **재기동**해야 반영된다(세션 시작 시점에만 읽는다).

> 🔎 **왜 API 로 재는가**: 봇 프로세스가 떠 있고 로그가 깨끗해도 "토큰 무효"·"초대 안 됨"은 **무반응**이라는 같은 증상으로 나타난다. 두 항목은 각각 한 줄 명령으로 갈리므로, 무반응을 만나기 전에 미리 재 두면 진단 분기가 통째로 사라진다. 반대로 이걸 안 재고 "떴으니 됐겠지"로 넘기면 Step 6.7 트러블슈팅을 처음부터 다시 돌게 된다.

---

## 트러블슈팅

| 증상 | 원인 | 대응 |
|---|---|---|
| `permission denied` on .env | chmod 미적용 | `chmod 600 "$BOT_DIR/.env"` |
| Discord 봇 토큰 invalid | 줄바꿈 포함 또는 reset 후 미저장 | 토큰 재 발급 + .env 한 줄 |
| 토큰 정상인데 서버 채널에서 무반응 (DM 은 됨) | Message Content Intent OFF | Developer Portal → Bot → Privileged Gateway Intents → Message Content Intent ON |
| 페어링 코드 만료 | 봇에 다시 DM | 새 코드 발급 |
| soul.md 안 inject | DISCORD_STATE_DIR 미export 또는 SessionStart hook 미등록 | `/thiscode:install-hooks` 먼저 실행 |
| 같은 봇 이름 디렉토리 충돌 | 이미 존재 | 다른 이름 또는 기존 정리 |
| 토큰·soul.md 정상인데 DM 무반응 | ①discord 플러그인 미설치 ②bun 미설치 ③`--channels` 플래그 누락 (실측 빈도순) | Step 6.7 선검사 3게이트 순서대로 — 플러그인 enable → bun 설치 → `--channels plugin:discord@claude-plugins-official` 포함 재시동 |
| Windows에서 chmod/permission 검증 실패 | NTFS 는 POSIX chmod 미적용 (정상) | 실패 무시 — 검증 항목에서 제외 |

---

## 관련 자원

- hook 등록: [install-hooks.md](install-hooks.md) — 반드시 본 명령 전에 실행
- DISCORD_STATE_DIR 구조: [../templates/discord-state-dir-README.md](../templates/discord-state-dir-README.md)
- soul.md template: [../templates/soul-general-assistant.md](../templates/soul-general-assistant.md)
- 규칙 시드 template (B3): [../templates/rules-seed.md](../templates/rules-seed.md) — copy-once, 절대 덮어쓰지 않음. 낡음 WARN = [../hooks/bot-session-init.sh](../hooks/bot-session-init.sh)
- 샘플 위키 (B4, WIKI_PATH 없을 때 안내): [../sample-vault/README.md](../sample-vault/README.md)
- 메인 wizard: [start.md](start.md)
