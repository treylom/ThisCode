# 옵시디언 에이전트 대시보드 — 5테마 디자인 시스템 + 플러그인 패턴

> 2026-06-01 `obsidian-ai-vault` 대시보드 플러그인에서 추출. ThisCode/ThisCodex 사용자가 자기 vault 대시보드에 재사용할 수 있는 **디자인 시스템 + 플러그인 골격**. vault 특화 데이터(봇·회의·gws)는 제외하고 재사용 가능한 부분만 일반화.

## 1. 아키텍처 — 생성↔표시 분리

플러그인은 **외부 호출 0**. vault-local JSON/md 만 읽어 렌더. 외부 데이터(캘린더·이동시간·봇 상태 등)는 **cron 스크립트가 JSON 생성**, 플러그인은 그 파일을 읽기만 한다.

```
[cron 스크립트] refresh.py ──쓰기──> 000-START-HERE/dashboard-data.json
[플러그인 main.ts] ──읽기(외부호출 0)──> 렌더
```

이 분리가 **cross-machine/윈도우 안전**의 핵심 — 플러그인은 토큰·API 없이 순수 렌더라 어느 기기에서나 동일 동작.

## 2. 5테마 (awesome-design 레퍼런스 기반 CSS 변수)

| 테마 | 무드 | canvas | 포인트색 | 폰트 |
|---|---|---|---|---|
| **Claude** | 따뜻·AI | `#faf9f5` | 코랄 `#cc785c` | serif+sans |
| **Linear** | 모던·다크 | `#010102` | 라벤더 `#828fff` | sans (음수 트래킹) |
| **Notion** | 친근·파스텔 | `#ffffff` | 퍼플 `#5645d4` | sans |
| **Stripe** | 컬러풀 | gradient | 인디고 `#533afd` | thin sans |
| **Raycast** | 미니멀·다크 | `#07080a` | 화이트 | Inter |

토큰 구조: `.agent-dashboard[data-theme="<name>"]{ --ag-canvas; --ag-card; --ag-ink; --ag-body; --ag-muted; --ag-primary; --ag-rule; --ag-shadow; --ag-fdisplay; --ag-fbody; ... }`. 전체 5테마 CSS = 동봉 `assets/agent-dashboard-themes.css`.

## 3. 플러그인 패턴 (Obsidian)

- `Plugin.onload`: `registerView` + `addRibbonIcon` + `addCommand` + **`addSettingTab`(테마 드롭다운)**.
- `ItemView.onOpen`: `contentEl.dataset.theme = settings.theme`.
- 설정 저장 = `saveData`/`loadData` (선택 테마 영속).
- **옵시디언 wrapper fix**(다크 테마 ↔ 라이트 모드 충돌 방지): `onOpen`에서 parent wrapper(`.view-content`)에 shell 클래스 + 테마별 canvas 배경을 직접 지정. 안 하면 라이트 테마에서 다크 테마 헤더 제목이 옵시디언 밝은 배경에 묻힘.

## 4. 세련화 원칙 ("AI 티" 벗기 — Linear/Vercel/Notion 레퍼런스)

- **selective accent**: 좌측 강조 바를 **강조 항목**(오늘·임박 D-day·미완료)에만. 모든 항목에 바를 두면 단조·"AI 생성물" 티. 나머지는 타이포 위계로 구분.
- **layered shadow**: inset highlight + ambient depth. 라이트 테마는 약하게, 다크는 깊게.
- **음수 트래킹**(`-0.01em`), **meta uppercase**, **hover micro-interaction**(`translateY(-1.5px)` + `cubic-bezier(0.16,1,0.3,1)`).
- **전용 renderer**: 배열을 ` · `로 join한 한 줄 ❌ → 시간(meta) + 제목 + 메모(sub) 구조 DOM 분리. 긴 항목은 `line-clamp:2` + 클릭 expand(hover tooltip보다 모바일/접근성 우위).

## 5. 이식 방법

1. `assets/agent-dashboard-themes.css`(5테마) + 본 패턴의 `main.ts` 스캐폴드를 자기 vault `.obsidian/plugins/<name>/` 에 복사.
2. 데이터 소스(JSON 생성 cron)는 자기 환경(캘린더·할일·원하는 위젯)에 맞춰 작성. 플러그인은 JSON 키만 맞으면 그대로 렌더.
3. `manifest.json`(`isDesktopOnly:false`) + esbuild 빌드.

> 원본: `obsidian-ai-vault/AI_Second_Brain/.obsidian/plugins/agent-dashboard/`. 본 문서는 재사용 골격이며, 봇 현황·회의 MOC·gws/TMAP 등 vault 특화 위젯은 원본 참고.
