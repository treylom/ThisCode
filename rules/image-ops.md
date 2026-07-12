# Rule: Image operations · reference-first · edit vs generate

Trigger: generating, editing, labeling, or dispatching image work.

## 1. Choose the operation
- **New composition** → text-to-image.
- **Edit an existing image** (preserve frame/layout/elements + change one thing) → image-to-image edit with the original image attached.
- **Deterministic overlay** (exact pixel preservation + mechanical text/labels) → PIL/ImageMagick. Do not paste plain fonts onto hand-drawn/illustrated art when visual tone matters.

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
