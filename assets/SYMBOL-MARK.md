# Symbol Mark — "Tofu"

A single character mark for the project, the way OpenClaw has its crab and
Claude Code has its symbol. One character, used by **both** ThisCode and
ThisCodex (they are companion runtimes of one system).

## The character

**Tofu** — a small, calm block of tofu with a friendly face and a tiny idea
spark. It is deliberately plain and soft: the system's whole idea is *quiet,
reliable helpers in the background*, not a loud robot.

Why tofu:

- It is the operator's long-running motif (the "말하는 두부 / 토푸경" writing
  persona, the 두부 color palette already used in the beginner guide).
- A block shape reads as a *building block* — the project's first-principles,
  "assemble it from small pieces" stance.
- Neutral and warm; it sits comfortably as a favicon, a README header, or a
  Discord avatar.

## Variants

| File | Use |
|---|---|
| `symbol-mark.svg` | ThisCode (Claude side) — the base Tofu |
| `symbol-mark-codex.svg` | ThisCodex (Codex side) — same Tofu, with a `</>` code bracket on the body to signal the code-verification companion |

Same body, same palette, same character — only the chest mark differs, so the
two repos are visibly one family.

## Palette (두부 / beige — matches the beginner-guide typst tokens)

| Token | Hex | Use |
|---|---|---|
| page beige | `#F3EAD7` | background plate |
| tofu top | `#FFFDF4` | lit top face |
| tofu front | `#FBF6EA` | front face |
| tofu side | `#F1E7D0` | shaded side |
| outline | `#6E5B43` | block edge |
| face | `#5E4D38` | eyes / smile |
| accent | `#C99A5B` | idea spark · codex bracket |

## Usage notes

- SVG is self-contained (no external fonts/refs) and scales cleanly; rasterize
  at need (e.g. 512×512 PNG for a Discord avatar).
- Keep the spark and (for the codex variant) the bracket in the accent color
  only — that is the single brand accent; don't recolor the body.
- If a future milestone wants motion (e.g. a blink), animate the two eye
  circles only; the block stays still.
