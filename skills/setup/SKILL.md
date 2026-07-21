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
3. Use tmux for Discord bot runtime windows on macOS/WSL/Linux. Do not use cmux
   for this flow. On Windows native (PowerShell), do NOT introduce
   tmux/WSL — follow `docs/10-windows-powershell-bots.md`: one PowerShell
   window per bot, and generate a `$PROFILE` function (e.g. `function mybot
   { $env:DISCORD_STATE_DIR=...; claude ... }`) as the alias equivalent.
4. Present safe mode first. YOLO/danger-full-access requires explicit opt-in.
5. Ask `progress_report_cadence`: `per_task`, `1m`, `3m`, `5m`, `off`, or
   `custom`. `per_task` means a meaningful subtask or milestone completion,
   not every raw model turn boundary.
6. Wire hooks: run `/thiscode:install-hooks` (safe `jq` merge into
   `~/.claude/settings.json`, existing hooks preserved). This registers the
   SessionStart helper (injects `soul.md` persona + working-dir memory index +
   the situational rules router `rules/INDEX.md`) and the active-meeting Stop
   reread (`hooks/meeting-stop-reread.sh`). Confirm SessionStart and Stop hooks
   are registered with the install-hooks verify step. Without this, recent
   rule / meeting-protocol behavior does not auto-apply.
7. Read `docs/RECENT-CHANGES.md` and apply anything not yet reflected — it is
   the newest-first digest of contract/behavior changes a fresh install must
   adopt (e.g. the Stop-hook output contract).
8. When aliases are generated, tell the user to `source` the generated alias
   script/block; only add it to a shell rc file if they explicitly want it
   permanent. On Windows the target is the PowerShell profile: write the
   function into `$PROFILE` and apply with `. $PROFILE` (if blocked by
   ExecutionPolicy, `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
   once).
9. Finish with `thiscode doctor` or the nearest available verify command.

## Guardrails

- Do not turn a copied skill into a completed setup claim.
- Missing decisions stop with the next command instead of guessed values.

---

## How to Use This Skill

Use this skill during initial setup phase to configure ThisCode environment. Handles dependency verification, environment detection, and configuration file generation for your specific OS and setup context.
