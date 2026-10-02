# Rule: Image operations · reference-first · edit vs generate

Trigger: generating, editing, labeling, or dispatching image work.

## 1. Choose the operation
- **New composition** → text-to-image.
- **Edit an existing image** (preserve frame/layout/elements + change one thing) → image-to-image edit with the original image attached.
- **Deterministic overlay** (exact pixel preservation + mechanical text/labels) → PIL/ImageMagick. Do not paste plain fonts onto hand-drawn/illustrated art when visual tone matters.

## 1.5 Type routing — diagrams, infographics, and text-heavy images: generation (GPT-image-2) is the first candidate (operator correction, 2026-08-23: "the image bot keeps misjudging what GPT-image-2 can do")
- **Diagrams, infographics, charts and graphs, posters, comics, summary cards, and images with (multilingual) text = GPT-image-2 generation is the first candidate.** The old assumption "diagrams must be built from design-system shapes, by hand, or by code rendering" is as outdated as §3's "Korean text goes on as an overlay" — do not force it in briefs or plans.
- Evidence (primary sources re-read by the orchestrator bot on 2026-08-23, plus a research bot's survey — internal notes, not shipped): ① OpenAI's announcement: "**Stronger structured generation (diagrams, infographics, charts, posters, comics) and improved multilingual text rendering**" (community.openai.com/t/introducing-gpt-image-2…/1379479) ② **#1 on the lmarena text-to-image leaderboard** (read directly on arena.ai — Arena Score 1381±5 · 70,065 votes · snapshot 2026-08-10; the score moved between 1360 and 1512 across snapshots, but **every source agreed on the #1 rank**). Priority for image benchmarks = **lmarena first, others second** (Artificial Analysis and similar = supporting labels only — the operator's call).
- **Types that require checking (not banned from generation — a person must check the output afterwards)**: ① precise **numeric** charts and graphs — no evidence found that the numbers come out accurate, so charts of real data stay code-rendered first (matplotlib and similar); use GPT-image-2 for conceptual or layout charts only ② composite assets that need a transparent background (reported as unsupported — decide after testing) ③ high-precision technical drawings and circuit diagrams (fidelity limits reported repeatedly) ④ character consistency across a multi-image series (frame drift observed). **Who records it, and where**: the bot that ordered the image runs the check **in the same turn** it collects the output (the same spot as §6 materialization verification), and appends a one-line result to the order record (the project's progress log or the order itself). Do not hand over output that has not been checked.
- Korean text = keep §3's generate-by-default rule, plus verbatim checking of the text after generation. **Korean field test, 2026-08-23 (2 images from the image bot + the orchestrator bot comparing magnified originals)**: everyday Korean (words with double final consonants, look-alike letter pairs, mixed text and numbers, a 72-character paragraph) = **rendered correctly (provisional — one card, one run)** / non-existent or rare syllable blocks and unfamiliar proper nouns = **silently swapped for a neighbouring syllable** (봟→밫 · 솗→솣 · 앍→앓 — 3 of 3). Because a swap does not "look broken", even a person reading the flow by eye misses it (the image bot's own first pass called everything "all correct" — a proven misjudgment). OCR catches it even less, because OCR itself normalizes to the expected syllable. → For coined words, transliterated foreign words, rare personal names, and non-existent syllable combinations, verbatim checking = a **letter-by-letter table** (the n-th source syllable ↔ the n-th syllable in the render, 1:1), not OCR — and **one self-check is never enough to declare "all correct"** (a second, independent check is required). The sample is one card, one run — do not generalize it into a single figure such as "Korean succeeds N% of the time".
- Relation to decks and slides: deck chrome and layout stay fixed to the design system (slide-deck §2.9); **content assets** (course maps, concept diagrams, infographics, summary cards) go through this section's routing and can be proposed as generation candidates.

## 1.6 Images with Korean (Hangul) text — prompting tips (adapted from ima2-gen 3.23.1, MIT, `skills/ima2/SKILL.md`)
- Put the exact Hangul string in quotes (`"오늘의 추천"`). Don't write a vague request such as "add some Korean text".
- Describe the scene in English and keep only the visible Hangul in Korean: `A clean summer poster with the exact Korean headline "여름 축제"`. The source cites practitioner testing: all-Korean prompts produced garbled Hangul, while English prompts with a quoted Korean string rendered correctly (a heuristic, not a guarantee).
- Start with short labels (titles, buttons) and leave body-length text for last. Hangul glyphs are complex, so long, dense paragraphs break most often.
- Name the typeface (`고딕체 (Gothic/Sans-serif)` or `명조체 (Myeongjo/Serif)`), the position (top center, bottom left), and the approximate size relative to the canvas. For mixed Korean and English, say which text goes where and at what level of hierarchy.
- After generation, verify the text as described in §1.5: check each character against the requested string, and don't treat one self-check as proof that all text is correct. This section covers what to do before generation; §1.5 covers checking afterwards.

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
