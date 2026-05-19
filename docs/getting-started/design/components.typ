// design/components.typ — 재사용 컴포넌트 (콜아웃 4종 + 코드블록 + 표 + 용어칩)
#import "tokens.typ": color, font, space

#let meta = (
  info:    (label: "참고",     fill: color.info),
  warning: (label: "주의",     fill: color.warning),
  success: (label: "체크포인트", fill: color.success),
  danger:  (label: "함정",     fill: color.danger),
)

#let callout(kind: "info", title: none, body) = {
  let item = meta.at(kind)
  let label = if title == none { item.label } else { title }
  block(
    width: 100%,
    fill: color.surface1,
    radius: 4pt,
    inset: (left: space.lg, right: space.lg, top: space.md, bottom: space.md),
    stroke: (left: 4pt + item.fill),
  )[
    #text(font: font.body, size: 8.5pt, weight: "bold",
          tracking: 0.6pt, fill: item.fill)[#upper(label)]
    #v(space.xs)
    #set text(font: font.body, size: 10pt, fill: color.body)
    #body
  ]
}

// body = 문자열 (markup [] 안에서 # 충돌 방지 위해 string 으로 받음)
#let codeblock(body, lang: none) = {
  block(
    width: 100%,
    fill: color.surface2,
    radius: 3pt,
    inset: (x: space.lg, y: space.md),
    stroke: (top: 0.5pt + color.hairline, bottom: 0.5pt + color.hairline),
  )[
    #set text(font: font.mono, size: 9pt, fill: color.ink)
    #raw(body, lang: lang, block: true)
  ]
}

// 용어 칩 — 어려운 영문/줄임말 첫 등장 시 쉬운 우리말 병기 (voice.md §4)
#let term(en, ko) = {
  box(inset: (x: 5pt, y: 1pt), radius: 3pt, fill: color.accent.lighten(78%))[
    #text(size: 9pt, weight: "bold", fill: color.accent)[#en]
    #text(size: 9pt, fill: color.muted)[· #ko]
  ]
}

#let table-clean(columns: 2, ..rows) = {
  table(
    columns: columns,
    inset: (x: space.md, y: space.sm),
    stroke: (x, y) => (
      top: if y == 0 { 0.8pt + color.ink } else { 0.4pt + color.hairline },
      bottom: 0.4pt + color.hairline,
      left: none, right: none,
    ),
    fill: (_, y) => if y == 0 { color.surface1 },
    ..rows.pos(),
  )
}

// 챕터 표지용 큰 번호 + 한/영 제목
#let chapter(no, ko, en) = {
  pagebreak(weak: true)
  block(breakable: false)[
    #text(font: font.serif, size: 40pt, fill: color.accent.lighten(35%))[#no]
    #v(space.xs)
    #text(font: font.body, size: 20pt, weight: "bold", fill: color.ink)[#ko]
    #v(space.xxs)
    #text(font: font.body, size: 11pt, fill: color.muted)[#en]
    #v(space.sm)
    #line(length: 100%, stroke: 1pt + color.accent)
    #v(space.md)
  ]
}
