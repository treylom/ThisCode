# Rule: Image operations · reference-first · edit vs generate

Trigger: generating, editing, labeling, or dispatching image work.

## 1. Choose the operation
- **New composition** → text-to-image.
- **Edit an existing image** (preserve frame/layout/elements + change one thing) → image-to-image edit with the original image attached.
- **Deterministic overlay** (exact pixel preservation + mechanical text/labels) → PIL/ImageMagick. Do not paste plain fonts onto hand-drawn/illustrated art when visual tone matters.

## 1.5 유형 라우팅 — 도식·인포그래픽·텍스트 이미지 = 생성(GPT-image-2) 1차 후보 (재경님 2026-08-23 r14 msg 1541063155281694851 — 「GD 의 GPT-image-2 에 대한 오해가 계속 있다」 정정)
- **도식·다이어그램·인포그래픽·차트·그래프·포스터·만화·정리 카드·(다국어) 텍스트 포함 이미지 = GPT-image-2(GD) 생성 1차 후보.** 「도식 = DS 도형/수작업/코드 렌더 고정」 전제 = §3 「한글은 오버레이」와 같은 낡은 전제 — 발주·기획에서 강제 ❌.
- 근거(카파시 1차 출처 직접 재열람 2026-08-23 + 코난 조사 `AI_Second_Brain/100-project/2026-08-23-part7-outline-slides/37-konan-gpt-image-2-strengths.md`): ① OpenAI 공식 「**Stronger structured generation (diagrams, infographics, charts, posters, comics) and improved multilingual text rendering**」(community.openai.com/t/introducing-gpt-image-2…/1379479) ② **lmarena text-to-image 리더보드 1위**(arena.ai 직접 열람 — Arena Score 1381±5·70,065표·스냅샷 2026-08-10. 점수는 스냅샷별 1360~1512 변동 관측, **1위 순위는 전 소스 일치**). 이미지 벤치 우선순위 = **lmarena > 기타**(Artificial Analysis 류 = 보조 라벨 — 재경님 명시).
- **검증 의무 동반 유형(생성 금지가 아니라 생성 후 사람 대조 의무)**: ① 정밀 «수치» 차트·그래프 — 숫자 정확도 보증 근거 미발견(37-doc ④): 실데이터 차트는 코드 렌더(matplotlib 류) 1차 유지, GPT-image-2 는 개념·구성 차트까지 ② 투명 배경 필요 합성 소재(미지원 지적 — 실측 후 판단) ③ 고정밀 기술 도면·회로도(fidelity 한계 반복 지적) ④ 다장 시리즈 캐릭터 일관성(프레임 드리프트 사례). **기입 주체·자리**: 대조 실행 = 그 이미지를 발주한 봇이 회수 «그 턴»에(§6 materialization 검증과 같은 자리), 결과 1줄 = 발주 기록(회의방 02-progress 또는 발주문)에 append — 대조 미실시 상태로 산출 전달 ❌.
- 한글 텍스트 = §3 생성 기본 그대로 + 생성 후 문구 verbatim 검증 유지(한글 «독립» 실사용 검증 사례는 미확인 라벨 — 37-doc 미확인 2).
- 덱·슬라이드와의 관계: 덱 chrome/레이아웃 = DS 불변(slide-deck §2.9), **콘텐츠 자산(코스 지도·개념 도식·인포그래픽·정리 카드)** 은 본 절 라우팅으로 GD 생성 후보 상신.

## 2. Reference-first hard gate
- Real people, brands, products, venues, screenshots, and other targets with a correct external appearance are **reference-first, no-imagination**.
- Before generation, collect a reference asset: path, URL, user attachment, message ID, official image, profile/avatar fetch, or existing screenshot.
- If a reference exists, do not use unconstrained text-to-image imagination. Use image-to-image or reference-conditioned generation, and name the identity invariants to preserve.
- If no reference exists, choose one: generic substitute, hold, or ask for confirmation. Do not invent a plausible face/logo/product.
- After the first identity error (wrong glasses, logo shape, product form, person likeness, etc.), stop re-prompting. Branch to reference-based img2img, substitute, or hold.

## 3. Trap signals
- User says "same image, only add/change X" → edit, not generation.
- Worrying about text rendering while doing an edit is a red flag that the wrong tool was chosen; text-to-image breaks text, deterministic overlay/editing does not.
- A blanket ban on image tools is wrong: the problem is unconstrained whole-image regeneration, not image-input editing.

## 4. Prompt and verification
- Edit prompt skeleton: "Edit this exact image. Keep frame/layout/elements 100% unchanged and inside frame. ONLY <change>. No redraw/recompose, no spill."
- Verify with source-vs-output comparison: unchanged regions should remain near-identical; only the intended edit/reference identity should change.

## 5. Dispatch contract
- The first dispatch message must name: edit vs generate, required reference path/URL/message, forbidden paths, expected output path, and verification criteria.

▶ Fill in: your image toolchain (edit-capable model, overlay tool) and where reference assets live.
