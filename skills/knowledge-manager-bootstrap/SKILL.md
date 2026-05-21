---
name: knowledge-manager-bootstrap
description: Use when installing the 4-Tier search stack for the first time, recovering from "search Tier X 실패", or recording vault_root with Obsidian CLI, vault-search MCP, and optional GraphRAG setup.
allowedTools: Bash, AskUserQuestion, Write, Read
---

# knowledge-manager-bootstrap

## Trigger
- Slash: `/thiscode:km-bootstrap`
- Failure escalation from `search` when all 4 Tiers fail

## Workflow

1. Detect environment: OS (uname -s), WSL (/proc/version), shell, claude version.
2. Detect existing assets:
   - Obsidian (`../../scripts/install-obsidian-cli.sh --check`)
   - vault-search MCP (`../../scripts/install-vault-search.sh --dry-run`)
   - GraphRAG server (`../../scripts/install-graphrag.sh --check`)
3. Detect vault_root candidates (cwd / $CLAUDE_DISCODE_VAULT env / `~/.thiscode-config` / `~/obsidian-ai-vault` / `~/Documents/Obsidian`).
4. AskUserQuestion 1회: vault_root 확정 (multiple choice from candidates + Other).
5. Write `~/.thiscode-config` with selected vault_root.
6. AskUserQuestion 1회: install matrix (Obsidian only / +vault-search MCP / +GraphRAG (full)).
7. Run corresponding `install-*.sh --apply` scripts in order.
8. Verify by calling `search` with sample query.
9. Print install summary + next-step suggestions.

## Config file format

`~/.thiscode-config`:
```yaml
vault_root: <vault>
search:
  tiers:
    - graphrag
    - obsidian
    - mcp
    - grep
  graphrag_endpoint: http://127.0.0.1:8400
km:
  variant: lite   # default Phase 1·2
  mode_r: false   # at variant only
```

See `references/setup-wizard.md` for exact AskUserQuestion prompts.

---

## How to Use This Skill

Use this skill when knowledge-manager reports "config missing" or when first setting up knowledge manager. It generates necessary configuration files and vault structure templates to prepare your vault for content ingestion.
