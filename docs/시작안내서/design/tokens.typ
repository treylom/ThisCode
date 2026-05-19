// design/tokens.typ — 의미 기반 디자인 토큰 (semantic-token-first)
// 베이지 배경 + 두부(tofu) 팔레트. design-md 원칙(의미 토큰 우선) 적용.

#let color = (
  canvas:   rgb("#fbf7ef"),  // 종이 배경 — 따뜻한 베이지
  surface1: rgb("#f4ecdd"),  // 콜아웃 바탕 — 두부 크림
  surface2: rgb("#efe7d6"),  // 코드 블록 바탕
  ink:      rgb("#2a2620"),  // 제목·강조 글자
  body:     rgb("#3f3a31"),  // 본문 글자
  muted:    rgb("#8a8170"),  // 보조 설명·영문 병기
  hairline: rgb("#ddd2bd"),  // 가는 구분선
  accent:   rgb("#cc785c"),  // 두부색 포인트 (tofu-orange)
  info:     rgb("#3b6f8f"),  // 참고
  warning:  rgb("#a86d16"),  // 주의
  success:  rgb("#4d7f52"),  // 체크포인트
  danger:   rgb("#b94a48"),  // 함정
)

#let space = (
  xxs: 2pt, xs: 4pt, sm: 6pt, md: 10pt,
  lg: 14pt, xl: 20pt, xxl: 28pt, section: 34pt,
)

// 시스템 가용 폰트로 고정 (Pretendard 미설치 환경 — Apple SD Gothic Neo 사용)
#let font = (
  body: ("Apple SD Gothic Neo", "NanumGothic"),
  serif: ("AppleMyungjo", "NanumMyeongjo"),
  mono: ("Menlo", "Apple SD Gothic Neo"),
)
