---
name: setup
description: Use when the user asks for /thiscode setup, step-by-step ThisCode onboarding, tmux-only Discord bot launch guidance, YOLO/safe-mode selection, or progress reporting cadence setup.
---

# ThisCode Setup Skill

Generated through the mandatory `/prompt` workflow:

```text
/prompt --batch GPT-5.6 상세 ThisCode setup skill: create a step-by-step installer-facing skill that invokes thiscode init, explains tmux-only Discord connection, safe-vs-YOLO mode, and asks progress_report_cadence.
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
6. Wire hooks: run the `/thiscode:install-hooks` skill (safe `jq` merge into
   `~/.claude/settings.json`, existing hooks preserved). This registers the
   SessionStart helper (injects `soul.md` persona + working-dir memory index +
   the situational rules router `rules/INDEX.md`) and the active-meeting Stop
   reread (`hooks/meeting-stop-reread.sh`). Confirm SessionStart and Stop hooks
   are registered with the install-hooks verify step. Without this, recent
   rule / meeting-protocol behavior does not auto-apply.
7. Read `docs/RECENT-CHANGES.md` and apply anything not yet reflected — it is
   the newest-first digest of contract/behavior changes a fresh install must
   adopt (e.g. the Stop-hook output contract).
8. Generate the shell aliases / launcher — **REQUIRED, never skip silently**
   (2026-08-12 regression fix: real setups were observed ending without this
   step; a setup with no alias is incomplete unless the user explicitly
   declined, and the decline must be recorded in the completion contract
   below). Then tell the user to `source` the generated alias
   script/block; only add it to a shell rc file if they explicitly want it
   permanent. On Windows the target is the PowerShell profile: write the
   function into `$PROFILE` and apply with `. $PROFILE` (if blocked by
   ExecutionPolicy, `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
   once).
9. Finish with `thiscode doctor` or the nearest available verify command, and
   echo the completion contract below in the final report.

## Completion Contract (yaml 규약 — 2026-08-12)

The final setup report MUST echo this block with real values. `aliases` may
never be empty or omitted — a silent skip reads as an incomplete setup:

```yaml
setup_completion:
  aliases: installed | declined(<reason>)   # step 8 — REQUIRED (bot 생성 흐름은 create-bot 의 $BOT_DIR/bot.yaml 이 정본)
  wd_docs: created | declined(<reason>)     # WD CLAUDE.md — create-bot Step 6 결과(bot.yaml wd_docs 와 동일, REQUIRED)
  hooks_wired: true                         # step 6 — install-hooks verify passed
  doctor: pass                              # step 9
```

## Guardrails

- Do not turn a copied skill into a completed setup claim.
- Missing decisions stop with the next command instead of guessed values.
- A setup report without the completion contract (or with `aliases` empty) is
  not a finished setup — go back and run the skipped step.

---

## How to Use This Skill

Use this skill during initial setup phase to configure ThisCode environment. Handles dependency verification, environment detection, and configuration file generation for your specific OS and setup context.
