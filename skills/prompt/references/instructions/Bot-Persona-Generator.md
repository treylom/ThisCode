# Bot-Persona-Generator — soul.md / CLAUDE.md / AGENTS.md 생성 프레임워크

> `/prompt bot-persona: <역할> <범위> <Discord 연동>` 로 호출되거나,
> SETUP-CONFIG-GUIDE §0 가이드 온보딩이 봇 메타 파일을 만들 때 이 레퍼런스를 따른다.
> 이 두 파일은 곧 **봇의 상시 프롬프트**다 — ad-hoc 작성 금지, 본 프레임워크로 생성.

## 산출물 (봇 1개당 2~3개 파일)

| 파일 | 역할 | 위치 |
|---|---|---|
| `soul.md` | 페르소나·말투·강제 규율 (SessionStart 주입) | `~/.claude/channels/discord-<bot>/soul.md` |
| `CLAUDE.md` | 봇 WD job sheet — 역할·경로·rules/INDEX.md 포인터 (Claude Code) | 봇 WD 루트 |
| `AGENTS.md` | CLAUDE.md 의 Codex 등가물 (Codex 봇이면 CLAUDE.md 대신) | 봇 WD 루트 |

## 생성 절차

1. **입력 수집 (부족하면 한 번에 하나씩 질문)**
   - 역할/도메인: 이 봇이 *소유*하는 일 vs *위임*하는 일
   - 페르소나: 이름·말투·시그니처 라인 (예: 보고 끝 `— <Bot Name>`)
   - 모델 id: 사용자의 하네스가 실제 노출하는 id 만 (지어내기 금지)
   - Discord: 채널/스레드 범위, 봇 user_id, 회의 스레드 규칙 적용 여부
   - vault 범위: 검색/쓰기 허용 경로, Obsidian 유무
2. **soul.md 생성** — 가장 가까운 `templates/soul-*.md` (research-bot /
   writing-bot / schedule-bot / general-assistant / custom) 를 베이스로:
   - frontmatter: `name` / `description` / `version` / `triggers` 필수
   - "강제 페르소나 규율" 섹션: 매 응답 자가점검 항목 (시그니처 포함) ≥ 3개
   - 비개발자 사용자가 주인이면 "쉬운 말 우선" 규율 명시
   - 개인 식별 정보(타인 실명·채널 id)는 placeholder 로
3. **CLAUDE.md / AGENTS.md 생성** — 얇게 (job sheet):
   - 봇 정체성 1줄 + WD 경로 + soul.md 로딩 순서
   - 운영 규칙은 인라인 금지 → `rules/INDEX.md` 포인터만
   - Codex 봇이면 AGENTS.md (`project_doc_fallback_filenames` 가 읽음)
4. **검증 후 완료 선언**
   - soul.md frontmatter 파싱 OK · 시그니처 라인 존재
   - meta 파일이 rules 본문을 인라인하지 않고 INDEX 만 가리킴
   - `<@본인 봇 ID>` 같은 placeholder 가 실값으로 치환됐는지 (Discord
     Developer Portal → Bot → Copy User ID 가 그 값)

## 안티패턴

- 규칙 전체를 CLAUDE.md 에 욱여넣기 (context bloat → recall 저하)
- 다른 사람·다른 봇의 고유명사/채널 id 를 템플릿에서 그대로 복사
- 존재하지 않는 모델 id·스킬 이름 발명
- soul.md 와 CLAUDE.md 에 같은 내용 중복 (drift 원인)
