# thiscode — Gemini CLI context

This is the Gemini CLI / multi-harness entry context for the `thiscode` plugin.

> thiscode brings a portable knowledge manager + 4-Tier vault search to any agentskills.io-compatible runtime.

## When to use

- Student needs to ingest a URL / file / inline text into a local markdown vault.
- Student asks a vault question and wants graded fallback (GraphRAG → Obsidian CLI → vault-search MCP → ripgrep).
- Student is debugging why search returns "Tier 4: 텍스트 검색 결과입니다" — invoke `/thiscode-km-bootstrap`.

## Layout (L3 — npm gemini-extension wrapper)

- `gemini-extension.json` — declares contextFileName + skill/command/contract dirs
- `GEMINI.md` (this file) — startup context
- `AGENTS.md` — multi-harness shared context (Claude / Gemini / OpenCode / Hermes)
- `package.json` — npm metadata (optional install via `npm i -g @treylom/thiscode`)
- skills/, commands/, contracts/, scripts/ — same dirs the Claude Code and Hermes wrappers consume

## Key facts

- **Single source of truth** for behavior: `contracts/search-fallback-4tier.md`, `contracts/km-mode-spec.md`, `contracts/km-variant-matrix.md`. Any client MUST follow these.
- **Variants** (`contracts/km-variant-matrix.md`): `lite` (default, Phase 1·2), `at` (Phase 3 Agent Teams), `plain` (headless).
- Drift detection: `bash scripts/km-version.sh` — compares plugin contracts vs vault mirror.

## Suggested first actions

1. `/thiscode-km-bootstrap` — install + wire 4-Tier stack.
2. `/thiscode:km` — shows how to install the km plugin, which provides ingestion and vault search.
