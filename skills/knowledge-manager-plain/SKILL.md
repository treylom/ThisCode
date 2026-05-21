---
name: knowledge-manager-plain
description: Use when running headless or non-interactive knowledge management without AskUserQuestion, especially when $CLAUDE_DISCODE_HEADLESS=1 or the user requests --variant plain.
allowedTools: Read, Write, WebFetch, Bash, Glob, Grep
---

# knowledge-manager-plain

> Implements Mode I from `contracts/km-mode-spec.md`. Plain variant per `contracts/km-variant-matrix.md` (no AskUserQuestion).

## Trigger
- $CLAUDE_DISCODE_HEADLESS=1 + any KM Mode I request
- `/thiscode:km --variant plain ...`

## Workflow

1. Read `~/.thiscode-config` for vault_root. If missing, write to `$HOME/Inbox/` with notice.
2. Extract (URL/file/text) — same as km-lite Step 2.
3. Generate frontmatter — same as km-lite Step 3, but auto-derive tags from title only (no AskUserQuestion).
4. Determine sub-folder: always `Inbox/`.
5. Write via `Write` tool only (no Obsidian CLI/MCP — even if present, skip for determinism).
6. Print stored path.

## Why no Obsidian even when present
Plain variant guarantees byte-identical output regardless of environment — important for batch ingestion and headless CI use.

---

## How to Use This Skill

Use this skill for straightforward knowledge management without Agent Teams or parallel processing. Supports Mode I (ingestion) and Mode R (reorganization). Good for single-note operations and when parallel execution is not needed.
