---
name: setup
description: Use when the user asks for /thiscode setup, step-by-step ThisCode onboarding, tmux-only Discord bot launch guidance, YOLO/safe-mode selection, or progress reporting cadence setup.
---

# ThisCode Setup Skill

Generated through the mandatory `/prompt` workflow:

```text
/prompt --batch GPT-5.5 상세 ThisCode setup skill: create a step-by-step installer-facing skill that invokes thiscode init, explains tmux-only Discord connection, safe-vs-YOLO mode, and asks progress_report_cadence.
```

## Goal

Guide `thiscode setup` / `thiscode init` through a reason-first setup path.

## Required Flow

1. Run `thiscode init` for guided setup.
2. Confirm repo root and any bot working directory before generating aliases.
3. Use tmux for Discord bot runtime windows. Do not use cmux for this flow.
4. Present safe mode first. YOLO/danger-full-access requires explicit opt-in.
5. Ask `progress_report_cadence`: `per_task`, `1m`, `3m`, `5m`, `off`, or
   `custom`. `per_task` means a meaningful subtask or milestone completion,
   not every raw model turn boundary.
6. When aliases are generated, tell the user to `source` the generated alias
   script/block; only add it to a shell rc file if they explicitly want it
   permanent.
7. Finish with `thiscode doctor` or the nearest available verify command.

## Guardrails

- Do not turn a copied skill into a completed setup claim.
- Missing decisions stop with the next command instead of guessed values.
