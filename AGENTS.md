# thiscode — Multi-harness Agent Context (AGENTS.md)

> Shared context for any agentskills.io-compatible runtime: Claude Code, Hermes Agent, Gemini CLI, OpenCode, Goose, Cursor, etc.

## What this plugin provides

- **Bot-harness operations**: setup/installers, meetings, shared memory, model routing, and Codex/Discord bridges.
- **Knowledge management and vault search are outside ThisCode 1.4.0**. Install the km plugin and use `/km:search`,
  `/km:knowledge-manager`, and `/km:setup` for those capabilities.

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
| `/thiscode:setup` | wizard | ThisCode bot-harness setup and local installer |

Knowledge management and vault-search setup are provided by the km plugin; follow its `/km:setup` documentation.

## Cross-harness invocation reference

- **Claude Code**: `Skill(<name>)` for any skill under `skills/`; vault search uses the km plugin (`/km:search`)
- **Hermes Agent**: the runtime registers the `on_session_start` drift-check hook; KM/search surfaces are not registered here
- **Gemini CLI**: read `GEMINI.md` on startup; skills auto-discovered from `skills/`
- **OpenCode / Goose / Cursor**: standard agentskills.io SKILL.md frontmatter (`name` + `description`) makes them visible
