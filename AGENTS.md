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

Versions are per contract: `search-fallback-4tier` is `0.2.0`;
`km-mode-spec`, `km-variant-matrix`, and `repo-handoff-install-contract` are
`0.1.0`. See each file's `contracts/*.md` frontmatter.

## Drift detection

```bash
bash scripts/km-version.sh
```

Compares plugin contracts vs the vault mirror at `<vault>/.claude/reference/contracts/`. Exits non-zero on any version mismatch.

## Claude Code entry points

| Entry point | Surface | Purpose |
|---|---|---|
| `/thiscode:add-bot` | `commands/add-bot.md` | Add a Discord bot to an existing setup |
| `/thiscode:codex-check` | `commands/codex-check.md` | Verify the Codex CLI bridge |
| `/thiscode:init` | `commands/init.md` | Detect the environment and run the selected ThisCode local setup scripts |
| `/thiscode:install-browser` | `commands/install-browser.md` | Install and verify the browser tool |
| `/thiscode:km-bootstrap` | `commands/km-bootstrap.md` | Point to ThisCode local search-tool scripts and km plugin setup |
| `/thiscode:km` | `commands/km.md` | Point to `/km:search` and `/km:knowledge-manager` |
| `/thiscode:open-meeting` | `commands/open-meeting.md` | Create the standard multi-bot meeting files |
| `/thiscode:slack-configure` | `commands/slack-configure.md` | Connect a Claude Code session to Slack |
| `/thiscode:start` | `commands/start.md` | Run the main Discord bot setup wizard |
| `/thiscode:test` | `commands/test.md` | Run feature smoke tests |

`/thiscode:setup` is the separate `skills/setup/SKILL.md` entry point, not a file under `commands/`. `/thiscode:install-hooks` is likewise the `skills/install-hooks/SKILL.md` skill, not a `commands/*.md` file. Knowledge management and vault-search behavior are provided by the km plugin; the two ThisCode `km*` commands above are migration pointers, not local implementations.

## Cross-harness invocation reference

- **Claude Code**: `Skill(<name>)` for any skill under `skills/`; vault search uses the km plugin (`/km:search`)
- **Hermes Agent**: the runtime registers the `on_session_start` drift-check hook; KM/search surfaces are not registered here
- **Gemini CLI**: read `GEMINI.md` on startup; skills auto-discovered from `skills/`
- **OpenCode / Goose / Cursor**: standard agentskills.io SKILL.md frontmatter (`name` + `description`) makes them visible
