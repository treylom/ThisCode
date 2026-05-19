#import "design/tokens.typ": color, font, space
#import "design/components.typ": callout, codeblock, term, table-clean, chapter

#set document(
  title: "ThisCode · ThisCodex 아주 쉬운 시작 안내서",
  author: "글재경 (옵시디언 어벤져스)",
)

#set page(
  width: 176mm,
  height: 235mm,
  margin: (outside: 24mm, inside: 20mm, y: 22mm),
  fill: color.canvas,
  numbering: "1",
  footer: context {
    set text(font: font.body, size: 8pt, fill: color.muted)
    if counter(page).get().first() > 1 [
      #line(length: 100%, stroke: 0.4pt + color.hairline)
      #v(2pt)
      #grid(columns: (1fr, auto),
        [ThisCode · ThisCodex 시작 안내서],
        [#counter(page).display()])
    ]
  },
)

#set text(font: font.body, size: 10.5pt, lang: "ko", fill: color.body)
#set par(justify: true, leading: 0.72em)
#set heading(numbering: none)

#show heading.where(level: 1): it => {
  v(space.lg)
  text(font: font.body, size: 14pt, weight: "bold", fill: color.ink)[#it.body]
  v(space.xs)
}
#show heading.where(level: 2): it => {
  v(space.md)
  text(font: font.body, size: 11.5pt, weight: "bold",
       fill: color.accent)[#it.body]
  v(space.xxs)
}

// ───────────────────────── 표지 ─────────────────────────
#v(4.5cm)
#align(center)[
  #text(font: font.serif, size: 13pt, fill: color.accent,
        tracking: 3pt)[OBSIDIAN AVENGERS · 시작 안내서]
  #v(0.9em)
  #text(font: font.body, size: 30pt, weight: "bold", fill: color.ink)[
    ThisCode · ThisCodex
  ]
  #v(0.3em)
  #text(font: font.body, size: 19pt, weight: "bold", fill: color.ink)[
    아주 쉬운 시작 안내서
  ]
  #v(0.5em)
  #text(font: font.body, size: 12pt, fill: color.muted)[
    The Very First Guide — for Absolute Beginners
  ]
  #v(2em)
  #line(length: 38%, stroke: 1.2pt + color.accent)
  #v(1.4em)
  #text(size: 10.5pt, fill: color.body)[
    한 번도 만져본 적 없는 분을 위한 한 권
  ]
  #v(0.3em)
  #text(size: 9pt, fill: color.muted)[
    2026-05-19 · 글재경 작성 · v1
  ]
]
#pagebreak()

// ───────────────────────── 들어가며 ─────────────────────────
= 들어가며 (Before We Start)

저는 이 글을 '터미널이 뭔지도 잘 모르겠는' 분을 떠올리며 씁니다. 그래서
어려운 말은 처음 나올 때마다 쉬운 우리말을 나란히 붙여 둘게요. 천천히
따라오시면 됩니다.

해서, 먼저 큰 그림 하나만요. 우리가 만든 건 *디스코드 채팅창에 말을
걸면, 그 안의 AI 비서들이 일을 해 주는 시스템*이에요. 그 비서들을 내
컴퓨터에 설치하고 깨우는 두 가지 꾸러미가 있는데, 이름이 이렇습니다.

#table-clean(
  columns: (auto, 1fr),
  [*이름*], [*한 줄 설명*],
  [#term("ThisCode", "디스코드")],
  [Claude(클로드) 기반 비서 꾸러미. 우리 팀 5봇의 기본 살림집],
  [#term("ThisCodex", "디스코드")],
  [Codex(코덱스, OpenAI 코딩 도구) 기반 비서 꾸러미. 코드 검증 담당],
)

#callout(kind: "info", title: "이 책의 약속")[
  외울 필요 없습니다. AI를 잘 쓰는 사람은 명령어를 외운 사람이 아니라,
  *지금 상태를 작게 확인하고 다음 한 걸음을 정할 수 있는* 사람이에요.
  이 책은 그 '작게 확인하는 법'을 알려 드립니다.
]

// ───────────────────────── 1장 ─────────────────────────
#chapter("1", "왜 디스코드인가", "Why Discord?")

== 메신저 하나로 AI를 부린다는 것

보통 AI 도구는 까만 화면(#term("terminal", "터미널 — 명령어 입력 창"))에
명령어를 쳐야 움직입니다. 초보자에게 이 까만 화면은 무섭죠. 그래서 우리는
*이미 익숙한 채팅 앱*인 디스코드를 창구로 골랐어요.

#table-clean(
  columns: (1fr, 1fr),
  [*까만 화면으로 쓸 때*], [*디스코드로 쓸 때*],
  [명령어를 정확히 외워야 함], [평소 말투로 부탁하면 됨],
  [컴퓨터 앞에 있어야 함], [폰에서도 메시지 한 줄로 가능],
  [결과가 화면에 흘러가 사라짐], [채팅 기록으로 계속 남음],
)

== 우리 팀에는 비서가 여럿입니다

한 명이 다 하지 않습니다. 역할별로 나뉜 *봇(bot, 자동 비서)* 들이
디스코드 채널에서 협업해요. 사람 팀처럼요.

#table-clean(
  columns: (auto, 1fr),
  [*비서*], [*맡은 일*],
  [코난], [자료조사 · 사실 확인 (Research)],
  [손석희], [코드 검증 · 리뷰 (Code review)],
  [스트레인지], [일정 · 알림 관리 (Schedule)],
  [글재경], [글쓰기 (Writing)],
  [카파시], [전체 조율 · 회의 진행 (Orchestration)],
)

#callout(kind: "success", title: "1장 체크포인트")[
  "디스코드 = 창구, 그 안에 역할별 비서 여럿" — 이 한 문장만 가져가세요.
]

// ───────────────────────── 2장 ─────────────────────────
#chapter("2", "어떤 봇을 켤까", "Which Bot Should I Run?")

== 상황으로 고르세요

봇 이름을 외우지 마세요. *"내가 지금 뭘 하고 싶은가"* 로 고릅니다.

#table-clean(
  columns: (1fr, auto),
  [*하고 싶은 일*], [*깨울 비서*],
  [자료를 찾아 정리하고 싶다], [코난],
  [내가 쓴 코드가 맞는지 봐 달라], [손석희],
  [언제 뭘 하기로 했는지 챙겨 달라], [스트레인지],
  [글·문서를 써 달라], [글재경],
  [여러 비서가 같이 움직여야 한다], [카파시(가 나머지를 부름)],
)

== 처음이라면 딱 하나만

다 켜지 마세요. 처음엔 *가장 자주 쓸 비서 하나*만 켜고 익숙해진 뒤
늘리는 게 좋아요. 보통은 자료조사(코난) 또는 글쓰기(글재경)부터
시작합니다.

#callout(kind: "warning", title: "한꺼번에 다 켜면")[
  비서가 많을수록 컴퓨터 자원을 더 쓰고, 누가 무슨 말을 했는지 헷갈립니다.
  *하나 → 익숙해짐 → 추가* 순서를 지키세요.
]

// ───────────────────────── 3장 ─────────────────────────
#chapter("3", "설치하기 (상황별 분기)", "Installation — Pick Your Path")

== 큰 흐름은 단 3걸음

세부 명령은 설치 도우미가 물어보며 진행합니다. 큰 그림만 알면 돼요.

#table-clean(
  columns: (auto, 1fr),
  [*걸음*], [*무엇을 하나*],
  [1. 꾸러미 받기], [ThisCode 또는 ThisCodex 파일을 내 컴퓨터에 내려받기],
  [2. 설치 도우미 실행], [도우미가 폴더·비서 위치를 *물어보며* 잡아 줌],
  [3. 디스코드 연결], [내 디스코드 채널과 비서를 이어 줌],
)

== 갈림길: 나는 어느 쪽?

#callout(kind: "info", title: "갈림길 A — Claude를 주로 쓴다")[
  *ThisCode* 를 설치합니다. 설치 도우미 이름은 `/thiscode:setup` 이에요.
  채팅창에 아래처럼 한 줄 부탁하면 도우미가 단계별로 안내합니다.
]

#codeblock("/thiscode:setup 을 실행해서 설치를 도와줘", lang: "text")

#callout(kind: "info", title: "갈림길 B — 코드 검증도 필요하다")[
  *ThisCodex* 를 추가합니다. 설치 명령은 아래 한 줄. `--apply` 는
  "확인만 하지 말고 실제로 적용해 줘"라는 뜻이에요.
]

#codeblock("thiscodex init --apply", lang: "bash")

#callout(kind: "warning", title: "도우미가 질문하면")[
  설치 도우미는 폴더 위치 같은 걸 *한 번에 하나씩* 물어봅니다. 모르면
  엔터(기본값)로 두어도 안전하게 멈추도록 만들어져 있어요. 겁내지 마세요.
]

#callout(kind: "success", title: "3장 체크포인트")[
  설치 = 받기 → 도우미 실행 → 디스코드 연결. 도우미가 *물어보며* 끌고
  갑니다. 외울 명령은 위 한두 줄뿐.
]

// ───────────────────────── 4장 ─────────────────────────
#chapter("4", "alias · yolo · discord", "Three Words You'll Hear")

자주 듣게 될 세 단어를 풀어 둘게요. 뜻만 알면 충분합니다.

== alias — 긴 명령을 짧은 별명으로

#term("alias", "별명") 은 길고 복잡한 명령에 *짧은 별명*을 붙이는 기능이에요.
예를 들어 비서를 깨우는 긴 명령을 `konan` 한 단어로 줄여 둡니다. 설치
도우미가 이 별명을 만들어 주고, 다음에도 쓰도록 기록해 둬요.

#codeblock("konan   # '코난 비서 깨우기' 긴 명령의 별명", lang: "bash")

== yolo — 매번 확인 안 받고 알아서

#term("yolo", "욜로 — 자동 진행 모드") 는 비서가 한 걸음마다 "해도 될까요?"
묻지 않고 *알아서 끝까지* 진행하게 하는 설정이에요. 빠르지만, 그만큼
비서를 믿고 맡기는 모드라 켤 때 한 번 물어봅니다.

#callout(kind: "danger", title: "yolo 함정")[
  편하다고 아무 데서나 켜지 마세요. 되돌리기 어려운 작업(파일 삭제 등)을
  자동으로 해버릴 수 있습니다. 처음엔 *끄고* 쓰다가 익숙해지면 켜세요.
]

== discord — 비서와 나를 잇는 통로

#term("discord", "디스코드") 연결은 "어느 채팅방의 비서가 내 말을 듣는가"를
정하는 일이에요. 한 번 이어 두면, 그 방에 글을 쓰는 것만으로 비서가
일합니다. 폰에서도요.

#callout(kind: "success", title: "4장 한 줄 정리")[
  alias(별명) = 명령 줄이기 · yolo(자동) = 끝까지 맡기기(주의) ·
  discord(연결) = 말 거는 통로 만들기.
]

// ───────────────────────── 5장 ─────────────────────────
#chapter("5", "메모리가 어떻게 일하나", "How the Memory Works")

== 비서도 '기억'을 합니다

대화가 끝나도 비서가 중요한 걸 잊지 않도록 *메모리(memory, 기억 저장소)*
가 있어요. 핵심은 두 가지입니다.

#table-clean(
  columns: (auto, 1fr),
  [*기억 종류*], [*무엇을 담나*],
  [공용 기억], [모든 비서가 같이 보는 사실 · 규칙 · 사용자 취향],
  [개인 기억], [그 비서만의 말투 · 실수 복기],
)

== 지금 방식과 더 나은 방식

지금은 세션이 시작될 때 공용 기억을 *통째로* 읽어 옵니다. 양이 많아지면
"다 기억은 하는데 정작 필요한 걸 못 꺼내는" 문제가 생겨요. 그래서 바깥의
잘 만든 메모리 시스템들을 조사해 더 나은 방식을 설계 중입니다.

#callout(kind: "info", title: "조사로 얻은 핵심 (쉽게)")[
  - *섞어 찾기가 표준* — 뜻으로 찾기 + 관계로 찾기를 같이 쓰는 게 요즘
    기본. 한 가지 방식만 쓰는 건 옛날 방식.
  - *시간을 다루는 게 차별점* — 오래된 기억을 지우지 말고 "이건 옛
    버전" 표시만 남기면 나중에 되짚기 좋음.
  - *기억은 진화* — 새 메모가 들어오면 기존 메모의 연결을 스스로
    업데이트하는 방식(A-MEM)이 우리 옵시디언 구조와 잘 맞음.
]

#callout(kind: "warning", title: "초보자가 기억할 점은 딱 하나")[
  메모리 내부 구조는 비서가 알아서 합니다. 사용자는 *"비서가 중요한 건
  기억하고, 오래된 건 지우지 않고 표시만 한다"* 정도만 알면 충분해요.
]

// ───────────────────────── 6장 ─────────────────────────
#chapter("6", "안 될 때 (트러블슈팅)", "Troubleshooting")

막혔다고 당황하지 마세요. *추측 말고, 위에서 아래로 좁히기.* 순서대로
하나씩 확인하면 대부분 풀립니다.

== 자주 만나는 4가지

#table-clean(
  columns: (1fr, 1fr),
  [*증상*], [*먼저 볼 곳*],
  [비서가 대답이 없다], [디스코드 연결이 살아 있는지 (4장)],
  ["명령을 못 찾는다"], [별명(alias)이 기록됐는지, 새 창을 열었는지],
  [한글이 깨져 보인다], [글꼴 설치 여부 (안내서 PDF는 시스템 글꼴 사용)],
  [비서가 엉뚱한 폴더를 건드린다], [설치 도우미를 다시 실행해 위치 재설정],
)

== 그래도 안 되면

#callout(kind: "info", title: "딱 세 줄만 확인")[
  1. 지금 올바른 폴더에 있나? · 2. 비서가 깨어 있나(디스코드에 응답)? ·
  3. 방금 무엇을 바꿨나? — 이 세 줄을 비서에게 그대로 알려 주면, 비서가
  나머지를 좁혀 줍니다.
]

#callout(kind: "danger", title: "하지 말 것")[
  안 된다고 같은 명령을 계속 반복하거나, 잘 모르는 삭제 명령을 따라
  치지 마세요. *무엇이 어떻게 안 되는지 한 줄로 적어* 비서에게 물어보는
  게 가장 빠릅니다.
]

#callout(kind: "success", title: "마지막 한 마디")[
  잘못된 폴더에서 20분 헤매는 것보다, 처음 10초 *"여기 맞아?"* 확인이
  낫습니다. 천천히, 작게 확인하며 가세요. — 글재경
]

#pagebreak()
#align(center)[
  #v(2cm)
  #text(font: font.serif, size: 11pt, fill: color.muted)[
    옵시디언 어벤져스 · ThisCode · ThisCodex
  ]
  #v(0.3em)
  #text(size: 9pt, fill: color.muted)[
    이 안내서는 마일스톤마다 갱신됩니다.
  ]
]
