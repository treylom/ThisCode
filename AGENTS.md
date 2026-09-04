# thiscode — Multi-harness Agent Context (AGENTS.md)

> Shared context for any agentskills.io-compatible runtime: Claude Code, Hermes Agent, Gemini CLI, OpenCode, Goose, Cursor, etc.

## What this plugin provides

- **KM ingestion** (Mode I/R/G per `contracts/km-mode-spec.md`)
- **4-Tier vault search** per `contracts/search-fallback-4tier.md`
- **3 variants** per `contracts/km-variant-matrix.md`: `lite` / `at` / `plain`

## Packaging layers

| Layer | Target | Entry | Status |
|---|---|---|---|
| **L1** | agentskills.io standard | `skills/*/SKILL.md` | shipped (v0.1.0) |
| **L2** | Hermes Agent | `hermes-plugin/plugin.yaml` + `__init__.py` | shipped (v0.2.0) |
| **L3** | Gemini CLI / npm | `gemini-extension.json` + `GEMINI.md` + `package.json` | shipped (v0.2.0) |
| **L3b** | Claude Code marketplace | `.claude-plugin/plugin.json` + `marketplace.json` | shipped (v0.1.0) |

## Contract version

`0.1.0` — see `contracts/*.md` frontmatter.

## Drift detection

```bash
bash scripts/km-version.sh
```

Compares plugin contracts vs the vault mirror at `<vault>/.claude/reference/contracts/`. Exits non-zero on any version mismatch.

## Slash commands

| Command | Variant | Purpose |
|---|---|---|
| `/thiscode:km` | auto-routes | Mode I/R/G dispatch (see km-variant-matrix) |
| `/thiscode:km-bootstrap` | wizard | First-time install + config write |

## Cross-harness invocation reference

- **Claude Code**: `Skill(<name>)` for any skill under `skills/` (vault search moved to the km plugin — `/km:search`)
- **Hermes Agent**: `claude_discode_search` tool (auto-registered via `hermes-plugin/__init__.py`)
- **Gemini CLI**: read `GEMINI.md` on startup; skills auto-discovered from `skills/`
- **OpenCode / Goose / Cursor**: standard agentskills.io SKILL.md frontmatter (`name` + `description`) makes them visible
