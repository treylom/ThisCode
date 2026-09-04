# thiscode — Gemini CLI context

This is the Gemini CLI / multi-harness entry context for the `thiscode` plugin.

> thiscode brings bot-harness operations to agentskills.io-compatible runtimes. Knowledge management and vault search
> are provided by the separate km plugin.

## When to use

- Student needs to configure the ThisCode bot harness, meetings, shared memory, or model routing.
- Student needs knowledge management or vault search — install the km plugin and follow its command documentation.

## Layout (L3 — npm gemini-extension wrapper)

- `gemini-extension.json` — declares contextFileName + skill/command/contract dirs
- `GEMINI.md` (this file) — startup context
- `AGENTS.md` — multi-harness shared context (Claude / Gemini / OpenCode / Hermes)
- `package.json` — npm metadata (optional install via `npm i -g @treylom/thiscode`)
- skills/, commands/, contracts/, scripts/ — same dirs the Claude Code and Hermes wrappers consume

## Key facts

- ThisCode's source of truth covers bot-harness operations and its installation contracts.
- KM behavior and command variants are documented by the km plugin; thiscode does not bundle those skills.
- Drift detection: `bash scripts/km-version.sh` — compares the remaining plugin contracts vs vault mirror.

## Suggested first actions

1. `/thiscode:setup` — configure the ThisCode bot harness and installer surfaces.
2. Install the km plugin, then follow `/km:setup`, `/km:search`, and `/km:knowledge-manager` in its documentation.
