---
description: List all available thiscode subcommands and when to use each
---

# /thiscode:help

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

Available subcommands for ThisCode plugin:

| Subcommand | When to use |
|---|---|
| `/thiscode:start` | Initial setup wizard — environment detection, Discord bot pairing, first conversation validation. Run this first on a new machine. |
| `/thiscode:init` | Alternative to start — minimal interactive setup. Good for experienced users who want guided but lightweight config. |
| `/thiscode:install-hooks` | Register SessionStart and UserPromptSubmit hooks to ~/.claude/settings.json. Run once before start if hooks are missing. |
| `/thiscode:create-bot` | Scaffold a new Discord bot directory with .env and soul.md template. Run this for each additional bot beyond the primary. |
| `/thiscode:add-bot` | Quick alias for create-bot — adds one more bot to your setup. |
| `/thiscode:open-meeting` | Create a meeting room folder structure (4-file template: 00-context, 01-spec, 02-progress, 03-outcome). Use before multi-bot collaboration sessions. |
| `/thiscode:km` | Knowledge manager router — intelligent variant selection (lite/at/plain) based on input. Main entry point for vault ingestion and organization. |
| `/thiscode:km-bootstrap` | Bootstrap knowledge manager config when km command reports "config missing". Generates necessary config files. |
| `/thiscode:search` | 4-tier vault search (GraphRAG → Obsidian CLI → vault-search MCP → ripgrep). Quick or deep modes available with `--quick` or `--deep` flags. |
| `/thiscode:test` | Run test suite — verify install completeness and feature health. |
| `/thiscode:codex-check` | Validate Codex CLI bridge connectivity and execution layer. Check before using Codex-based parallel execution. |
| `/thiscode:self-update` | Pull latest ThisCode updates from GitHub. Recommended at session start to stay current. |

## Learn More

- **Setup guide**: [docs/SETUP.md](../docs/SETUP.md)
- **Beginner guide**: [docs/SETUP-BEGINNER.md](../docs/SETUP-BEGINNER.md)
- **Config guide**: [docs/SETUP-CONFIG-GUIDE.md](../docs/SETUP-CONFIG-GUIDE.md)
- **Recent changes**: [docs/RECENT-CHANGES.md](../docs/RECENT-CHANGES.md)

For detailed help on any subcommand, pass `--help` (if available) or refer to the docs.
