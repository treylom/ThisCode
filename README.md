![ThisCode — Tofu](assets/readme-banner.png)

# ThisCode

> **Role boundary**: ThisCode is the bot-harness operations bundle (operating rules, GraphRAG ops vendor, deployment contracts). The general-purpose knowledge product is [knowledge-manager](https://github.com/treylom/knowledge-manager); plugin installs go through [tofukyung-plugins](https://github.com/treylom/tofukyung-plugins).

> Knowledge management and vault search are provided by the **knowledge-manager** plugin — install it with `claude plugin marketplace add treylom/tofukyung-plugins` + `claude plugin install km@tofukyung-plugins`, then use `/km:search` and `/km:knowledge-manager`. ThisCode 1.4.0 no longer bundles its own copies of these skills.

> Claude Code + Discord bot + Codex CLI bridge plugin — personal vault automation + multi-agent ops.
>
> 🇰🇷 **한국어 버전**: [README.ko.md](README.ko.md) · 📘 **Setup**: [docs/SETUP.md](docs/SETUP.md) (developer) · 🌱 [docs/SETUP-BEGINNER.md](docs/SETUP-BEGINNER.md) (beginner) · 🧩 [docs/AGENTS.md](docs/AGENTS.md) (Custom Hybrid v1.0) · ⚙️ **[Config Guide](docs/SETUP-CONFIG-GUIDE.md)** (CLAUDE.md · soul.md · rules · Skills 2.0) · 🆕 **[Recent changes](docs/RECENT-CHANGES.md)** (read on install — newest-first digest the install AI should auto-reflect) · 📖 **[Getting started guide (English PDF)](docs/getting-started/ThisCode-ThisCodex-getting-started.en.pdf)** (beginner, 14p) · 📄 **[전체 정리 한 장 (HTML)](docs/SUMMARY.html)** · 🤝 **[ThisCodex](https://github.com/treylom/ThisCodex)** (Codex companion)

## Install With Your AI Assistant

Copy this into Claude Code or Codex:

```text
Follow the install files in https://github.com/treylom/ThisCode step by step. Start from README.md, run the guided setup, ask me before touching credentials or system packages, and finish by running the documented verification commands.
```

![ThisCode core idea — a structured Obsidian vault, the right bot per working directory, driven from Discord, bots collaborating](assets/core-mental-model.png)

> **New here?** Core idea: keep a **structured Obsidian vault**, put the **right bot in each working directory**, drive them from **Discord**, and let the bots coordinate with each other. Shared memory / search are supporting payoffs — not the headline. Start with the Setup links above — no prior knowledge assumed.

![ThisCode + ThisCodex detailed wiring (tmux · app-server · Discord · vault)](assets/architecture.png)

`bash install.sh` boots a Claude Code + tmux environment (WSL / Linux / macOS). **Core value**: a *structured Obsidian vault* where each working directory gets an *appropriate bot*, all usable from *Discord*, with bots that can *talk to each other*. The km plugin owns vault retrieval; thiscode's LLM model routing and bot operations make those bots useful — supporting, not the point.

> **Before you start (recommended):** (1) lay out your Obsidian **folder structure** first; (2) **install Obsidian** for full memory + internal-search. **No Obsidian?** You can still wire a plain Discord bot for connectivity only — but vault memory and internal-search quality are **not guaranteed** without it.

## 🛠️ Zero-config Install

**Prerequisite:** Claude Code CLI already installed + authenticated (https://claude.ai/code). The `install-superpowers.sh` step inside `install.sh` invokes the `claude` CLI.

For learners who prefer **single-command setup** (no wizard, no choices):

```bash
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode
cd ~/.claude/plugins/thiscode
bash scripts/install.sh --apply
```

This single command installs:

1. **superpowers** plugin (via Claude Code plugin manager)
2. **ripgrep** (Tier 4 baseline — brew / apt / dnf / apk multi-pkg-manager fallback)
3. **Obsidian CLI** detection (Tier 3 — manual download guide if missing)
4. **GraphRAG core** (Tier 1 — vendored Python runtime + 7-pkg pip install)
5. **Dense embedding** (Optional 4-channel — user confirms once, ~1GB)

After install: `bash scripts/healthcheck.sh` (6-phase verification: superpowers + ripgrep + obsidian-cli + vault-search MCP + GraphRAG + Dense embedding).

**Windows users:** two paths. **(a) Bot pairing only** — native **PowerShell works today**: Claude Code + the Discord plugin's *channels* directories (`~/.claude/channels/discord-<bot>/`) need **no tmux, no cmux, no daemon**; a bot session is just a PowerShell window running `claude` with `DISCORD_STATE_DIR` set ([docs/10-windows-powershell-bots.md](docs/10-windows-powershell-bots.md)). **(b) Full `install.sh` environment** (oh-my-tmux, multi-session helpers) — WSL 2 (Ubuntu 22.04+). If an AI assistant is driving your install on Windows, point it at path (a) — it must not try to recreate tmux with daemons or background services.

**Dependency provenance:** full attribution matrix (20 entries — Plugin 1 + Spec doc 2 + External tools 8 + optional GUI guide 1 + Optional Dense 3 + Vendored Python runtime 1 + Vendored prompt skill 1 + Vendored Slack bridge 1 + Vendored vault-search MCP 1 + thiscode 1) in [ATTRIBUTIONS.md](ATTRIBUTIONS.md). Cross-license compatibility verified by Phase 1 GPT-5.5 review (MIT + Apache 2.0 + BSD-3 + Unlicense — all permissive, copyleft zero); the Slack bridge entry is MIT by copyright-holder decision (2026-08-06), matching this repo.

**Lessons learned (consolidated into the v1.0 first integrated release):** This cycle's learnings are persisted in the vault under `AI_Second_Brain/.claude-memory/shared/feedback_*`:
- `feedback_no_student_term` — learner / user / participant terminology
- `feedback_autonomy_mode_no_option_questions` — autonomous cycle asks zero option-confirmation questions
- `feedback_no_turn_marker_continuous_execution` — zero turn-boundary utterances, continuous execution
- `feedback_background_task_proactive_polling` — background tasks require active polling (zero auto-notification assumption)
- `feedback_debugging_via_codex` — debugging tasks must be delegated to codex
- `feedback_fresh_env_actual_install_verification` — Phase 1+2 static review is limited; Phase 3 actual install is required ⭐ critical
- `feedback_tofu_at_codex_actual_mechanism` — multi-axis parallel = `/tofu-at-codex` (Agent Teams + sonnet workers)
- `feedback_sonnet_codex_debate_opus_synthesis` — sonnet ↔ codex multi-round debate → opus synthesis mechanism
- `feedback_no_user_decision_zone_autonomous` — zero "user decision zone" classification inside autonomous cycle (autonomy 3rd reinforcement)

## 🚀 Quickstart (vault-first)

```bash
# 1. Install thiscode as a Claude Code plugin
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode

# 2. Run the wizard — auto-detects env + recommends a Phase
bash ~/.claude/plugins/thiscode/scripts/claude-discode-init.sh

# Or inside Claude Code:
/thiscode:init
```

> **Plugin-marketplace path: verified working.** ThisCode ships a valid
> `.claude-plugin/marketplace.json` + `plugin.json`, and `claude plugin
> marketplace add` is a real Claude Code CLI command — so the marketplace path
> is **a supported install path, verified working end-to-end** (a real WSL run
> via `/plugin marketplace add treylom/ThisCode` → `/plugin install
> thiscode@thiscode-marketplace` → `/reload-plugins` loaded *5 plugins · 23
> skills · 8 agents · 4 hooks*) (that run predates 1.3.0; the plugin now ships
> 7 hooks via `hooks/hooks.json` — see `/thiscode:install-hooks`):
>
> ```
> /plugin marketplace add treylom/ThisCode
> /plugin install thiscode@thiscode-marketplace
> ```
>
> The `git clone` + wizard above (or `/thiscode:init`) is an equally supported
> alternative — prefer it when you want a writable clone (e.g. for
> `/thiscode:self-update`). (Codex side: the equivalent `codex plugin` path is
> **verified broken** on codex 0.130 — different harness — see ThisCodex.)

The wizard detects your vault state / installed tools / resource limits, then recommends an **8-Phase progressive journey**:

- **Phase 1–2**: immediate (ripgrep + obsidian-cli)
- **Phase 3**: 100+ notes → vault-search MCP recommended
- **Phase 4**: 500+ notes (recommended) / 1000+ (strongly recommended) / always optional (GraphRAG)
- **Phase 5**: 2000+ notes → km-at **Mode R preflight** (read-only diagnostics, dry-run apply)
- **Phase 6–7**: advanced (Dashboard / 4-channel hybrid retrieval)

> **GraphRAG = env-detected + opt-in** (user-spec). Force install is permitted even when note count is below the heuristic threshold.

## 💬 Plugin Commands & Skills Help

Each plugin command and skill has built-in help documentation:

### Plugin Commands

Claude Code exposes **both** `commands/*.md` and `skills/<name>/SKILL.md` as slash commands. Run `/thiscode:help` inside Claude Code for the full list with descriptions — it enumerates both surfaces from disk at run time, so it stays correct as commands are added. (You can also type `/` and filter by `thiscode:`.) Representative entry points:

- `/thiscode:start` — Initial setup wizard (environment detection, bot pairing, validation)
- `/thiscode:init` — Alternative lightweight setup for experienced users
- `/thiscode:create-bot` — Create a new Discord bot with soul.md template
- `/thiscode:create-slack-bot` — Connect a bot to Slack instead of (or in addition to) Discord (automates the claude-channel-server bridge; alias: `/thiscode:slack-configure`)
- `/thiscode:km` — Pointer to the knowledge-manager plugin (`/km:knowledge-manager`)
- `/thiscode:open-meeting` — Create meeting room structure for multi-bot collaboration
- `/thiscode:codex-check` — Validate Codex CLI bridge connectivity
- `/thiscode:install-hooks` — Check the SessionStart / UserPromptSubmit / PreToolUse / Stop hooks (**installing the plugin registers them** via the bundled `hooks/hooks.json`). Every hook runs **only in bot sessions** — when `DISCORD_STATE_DIR` is set; other sessions see no output and no behavior change. On a plugin install this command verifies the registration and clears leftovers from the older `~/.claude/settings.json` merge (which would otherwise fire the same hook twice); on a checkout without `hooks/hooks.json` it still performs that merge. `/thiscode:create-bot` runs the same `scripts/install-hooks.sh` for you.
- … and more — `/thiscode:help` lists every command with its description

### Skills

Each skill (bootstrap, init, meetings, shared-memory, etc.) includes a **"How to Use This Skill"** section in its SKILL.md. These explain when to invoke each skill and what it does. Knowledge management and vault search skills are no longer bundled here — install the knowledge-manager plugin and use `/km:knowledge-manager` and `/km:search`.

---

## Optional: Discord bot + Agent Teams

Discord bot integration and tmux-based Agent Teams are **opt-in extras**. The km plugin's vault retrieval works independently — Discord pairing is for advanced multi-bot orchestration.

> **Prefer Slack?** You can pair a bot over Slack instead of (or in addition to) Discord — run `/thiscode:create-slack-bot` (alias: `/thiscode:slack-configure`); it walks you through the human gates (CLI login, workspace install approval, token paste) and automates the rest. Details: [skills/slack-configure/SKILL.md](skills/slack-configure/SKILL.md). Ops & troubleshooting reference: [skills/slack-bridge/SKILL.md](skills/slack-bridge/SKILL.md).

### What you can do from Discord

Once a bot is paired, Discord becomes a remote control for your vault bots — no terminal needed:

- **💬 Hand off a task by mention** — `@bot summarize today's notes`; the bot works in its own session and replies in the channel.
- **🧵 Hold a meeting in a thread** — spin a thread for multi-bot collaboration; each bot reads/writes a shared meeting doc.
- **⏰ Wake an idle bot** — a channel message re-engages a bot whose session went quiet (signal via the channel, never by injecting into its tmux — see `rules/discord-comms.md` §5).
- **📎 Send files & images** — attach a screenshot or doc; the bot downloads it and works on it.
- **🧹 Tidy a session** — a human operator can send harness session-meta commands (`/compact`, `/clear`) straight into a bot's tmux session to manage its context (`rules/discord-comms.md` §5 R5).

> Everyday moves. For the fuller channel-mode session model (Admin / Main / Session routing), see [`docs/connector-session-ux.md`](docs/connector-session-ux.md).

---

## 📊 4-Tier Search Benchmark

How does thiscode's 4-Tier search trade off against vanilla `obsidian-cli` / `/search` / `/vault-search`? Measured on 5 axes. **Measure it against your own vault** — the headline numbers below are aggregates; your hardware / vault size / content distribution will shift them.

```bash
# Measure against your own vault (Tier 1 GraphRAG requires a running server)
VAULT=~/path/to/your/vault bash benchmark/runners/run-all.sh
python3 benchmark/report-generator.py --print-only
```

Numbers vary widely by vault size, content, and hardware — v1.0 ships the
runner and methodology rather than fixed benchmark figures. Run the script
above against your own vault to get meaningful numbers.

> Method / interpretation / your-own-fixture guide: [docs/BENCHMARK.md](docs/BENCHMARK.md). CI auto-runs Tier 4 ripgrep + sample fixture: [benchmark/results/](benchmark/results/).

---

## 🧠 LLM model routing

After retrieval, thiscode picks a model by task complexity:

| Task | Claude users | GPT / [Codex](docs/GLOSSARY.md#codex) users |
|---|---|---|
| Simple (factual lookup) | Haiku | gpt-5.5 |
| Medium (summary / classification) | Sonnet | gpt-5.5-codex |
| Synthesis (multi-doc reasoning) | Opus[1m] | gpt-5.5-codex-spark |

`scripts/route-model.mjs` heuristic — query length + keyword classifier. User override: `--model haiku|sonnet|opus`.

**Tier order:** Tier 1 [GraphRAG](docs/SETUP.md#tier-1) → Tier 2 [vault-search MCP](docs/SETUP.md#tier-2) → Tier 3 [Obsidian CLI](docs/SETUP.md#tier-3) → Tier 4 [ripgrep](docs/SETUP.md#tier-4). Accuracy-first fallback.

## 📚 Lost on terms? → [GLOSSARY.md](docs/GLOSSARY.md)

30+ terms (LLM / MCP / CEL / embedding / recall@5 / kg_depth / fallback / dispatcher / etc.).

---

## 🚀 Quick Start (3 steps — legacy Discord path)

### Step 1. Env detect + auto install

```bash
curl -fsSL https://raw.githubusercontent.com/treylom/ThisCode/main/install.sh | bash
```

Or git clone then run locally:

```bash
git clone https://github.com/treylom/ThisCode.git ~/code/thiscode
cd ~/code/thiscode && bash install.sh
```

`install.sh` runs 10 steps:

| Step | Action | Dependency |
|---|---|---|
| 1 | OS / Distro detect (WSL / Linux / macOS) | uname |
| 2 | Base packages (tmux + git + curl + jq + build-essential) | apt / dnf / yum / brew / pacman |
| 3 | nvm + Node.js LTS | curl |
| 4 | Claude Code global install | npm |
| 4.5 | **Codex CLI** (`@openai/codex`) global install — bridge dependency | npm |
| 5 | oh-my-tmux (`gpakosz/.tmux`) auto install | git |
| 6 | (optional) thiscode `tmux.conf.local` apply | user confirm |
| 6.5 | **Obsidian CLI** (Mac brew cask / WSL Windows native / Linux snap·flatpak·deb) — Tier 3 fallback | brew / snap / manual |
| 7 | Claude Code plugin install guidance (marketplace + slash commands) | (slash inside Claude Code) |
| 8 | First bot wizard guidance (`/thiscode:start`) | (slash inside Claude Code) |

Plugin slash commands auto-detected after install:

- `/thiscode:init` — **onboarding wizard** (env detect + 8-Phase recommend)
- `/thiscode:start` — main wizard (env detect + bot setup + first conversation)
- `/thiscode:install-hooks` — verify the SessionStart + UserPromptSubmit + **Stop (active-meeting reread)** hooks the plugin already registered via `hooks/hooks.json`, and clear any leftover `~/.claude/settings.json` merge from the older path (SessionStart injects soul.md + memory + `rules/INDEX.md`; the Stop hook is how recent rule/meeting changes auto-apply — see [docs/RECENT-CHANGES.md](docs/RECENT-CHANGES.md)). The hooks stay silent outside bot sessions.
- `/thiscode:create-bot` — new bot directory + .env + soul.md template
- `/thiscode:create-discord-bot` — add one additional Discord bot (alias: `/thiscode:add-bot`)
- `/thiscode:create-slack-bot` — connect a Slack workspace (automates the claude-channel-server bridge; alias: `/thiscode:slack-configure`)
- `/thiscode:open-meeting` — create a meeting folder (multi-bot 4-file standard)
- `/thiscode:codex-check` — Codex CLI bridge verification
- `/thiscode:self-update` — self-update check (git fetch behind)

Pristine Claude Code bootstrap (no hooks, no bots yet):

```
1. /thiscode:install-hooks   # Verify the SessionStart + UserPromptSubmit + Stop (meeting reread) hooks the install registered
2. /thiscode:create-bot      # First bot directory + soul.md setup
3. /thiscode:start           # Main wizard (Discord pairing + first conversation)
4. /thiscode:codex-check     # Verify Codex CLI active (optional)
```

## 📦 Operations know-how guide (docs/)

thiscode bundles the author's vault operations playbook:

- [03-shared-memory.md](docs/03-shared-memory.md) — **4-tier shared memory** (T1 git-tracked / T2 machine-specific / T3 project-meetings / T4 per-bot WD)
- [memory-dreaming.md](docs/memory-dreaming.md) — **reversible memory archival** (plain-language): periodic, *move-not-delete* cleanup that ships idle memory to out-of-WD cold storage with one-command checksum-verified restore. One tier-agnostic rubric across all tiers incl. Codex; conservative (auto-archive gated, ambiguous → human review); criteria self-correct from restores. Tool: `scripts/memory_dreaming.py` (`--scan` default dry-run / `--apply` gated / `--restore` / `--recalibrate`), weekly-enforced (YAML manifest + session-start overdue check + launchd)
- **orchestrator-watchdog** (`scripts/meeting_watchdog.py`) — **meeting progress watchdog (recommended on every meeting — invite one watchdog bot per meeting, start before the first dispatch)**: on meeting-thread creation a YAML-enforced watchdog checks progress every ~5 min and self-terminates only when the goal AND all tasks complete (models Claude Code `/goal`). `start`/`beat`/`check`/`status`/`stop`; fail-closed = keep-active (never falsely terminate a live meeting); pairs with [05-meeting-thread-protocol.md](docs/05-meeting-thread-protocol.md) §2.3 + [rules/meeting-protocol.md](rules/meeting-protocol.md) §5
- [04-obsidian-cli.md](docs/04-obsidian-cli.md) — **Obsidian CLI setup** (Mac brew / WSL Windows native / Linux snap·flatpak·deb) + 3-Tier fallback (CLI → MCP → Write/Read/Grep) + known bugs / workarounds
- [05-meeting-thread-protocol.md](docs/05-meeting-thread-protocol.md) — **meeting thread & channel governance** (new topic = new thread / archive final deliverables only / cross-machine = multiverse)
- [06-claude-code-server.md](docs/06-claude-code-server.md) — **Claude Code server modes** (`claude -p` headless + MCP server + tmux session vs headless split pattern)
- [08-debug-노하우.md](docs/08-debug-노하우.md) — **24+ debugging categories** (Workflow / Code Review / Vault Path / Meeting protocol / Security / Time / LLM Prompt / Schedule / Plugins / External Apps / Cross-bot SoP) — Korean only, dense operational learnings

### Step 2. Claude Code authentication

```bash
claude auth login    # 🐧 👤 → browser-based authentication
```

### Step 3. First bot wizard

```bash
tmux new-session -s claude                # 🐧 👤
cd ~/<project> && claude                  # 🐧 🤖
```

Inside Claude Code:

```
/thiscode:start                     # 🤖 wizard entry
```

The wizard walks you through Discord bot creation (Developer Portal), token entry, persona selection (`soul.md` template), and pairing + first conversation verification.

---

## 📚 Command icon legend

| Icon | Meaning |
|---|---|
| 🖥️ | Windows PowerShell |
| 🐧 | WSL Ubuntu / Linux terminal |
| 🤖 | Claude Code executes automatically |
| 👤 | User types directly |
| ✅ | Success |
| ❌→✅ | Failure followed by recovery |

---

## 🧩 Repository structure

```
thiscode/
├── install.sh                            # Env auto-detect + 10-step automation
├── README.md                              # This file (English, default)
├── README.ko.md                           # Korean version
├── LICENSE                                # MIT
├── .claude-plugin/
│   ├── marketplace.json                   # thiscode-marketplace
│   └── plugin.json
├── commands/                              # Slash discovery surface ① (incl. /thiscode:init)
├── skills/                                # Slash discovery surface ② — skills are callable as
│                                          #   /thiscode:<name> too (vault-mirror policy)
│   ├── codex-exec-bridge/                 # vault skill mirror (folder)
│   ├── init/                              # onboarding wizard skill
│   ├── bootstrap/                         # plugin install wizard
│   ├── meetings/                          # 4-file meeting protocol
│   ├── shared-memory/                     # 4-tier memory policy
│   └── …                                  # run /thiscode:help for the full list
├── hooks/                                 # Bot operations hooks
├── templates/                             # 5 soul personas + bot-roles-matrix · bot-checkup-checklist
├── configs/                               # tmux.conf.local
├── benchmark/                             # 4-Tier benchmark (run-all.sh + fixtures)
├── contracts/                             # search-fallback-4tier.md
├── schemas/                               # agent-spec.json (Custom Hybrid v1.0)
├── scripts/                               # install-graphrag.sh / install-obsidian-cli.sh / route-model.mjs
└── docs/                                  # SETUP / SETUP-BEGINNER / AGENTS / GLOSSARY / BENCHMARK / ARCHITECTURE / MANUAL
```

`templates/bot-checkup-checklist.md` — 7-item self-checkup that your bot behaves as written (run once after creating a bot, then monthly).

---

## 🎯 Use cases

### Scenario A. Zero-state setup on a fresh machine

Fresh WSL Ubuntu or macOS, setting up Claude Code for the first time.

```bash
curl -fsSL https://raw.githubusercontent.com/treylom/ThisCode/main/install.sh | bash
```

### Scenario B. Add Discord bot to an existing Claude Code user

Pair a Discord bot with a custom persona — Write `soul.md`, create the bot, run `/thiscode:start`.

### Scenario C. New adopter — self-paced

Follow the wizard. The 8-Phase journey takes you from ripgrep-only to GraphRAG-with-Mode-R-preflight at your own pace.

---

## 🔧 Compatibility

| Environment | Support | Notes |
|---|---|---|
| **WSL Ubuntu 20.04+** | ✅ primary | `install.sh` most-tested target |
| **Linux native** (Debian / Ubuntu / Fedora / Arch) | ✅ | Package manager auto-detected |
| **macOS** | ✅ | brew-based |
| **Windows native (PowerShell)** | ✅ bot pairing | Discord-bot pairing runs natively via Claude Code **channels** (`~/.claude/channels/`) — **no tmux / cmux / daemon needed**. Only the tmux-based extras (oh-my-tmux, multi-session helpers in `install.sh`) still want WSL — see [docs/10-windows-powershell-bots.md](docs/10-windows-powershell-bots.md) |

| Agent runtime | Compatibility | Notes |
|---|---|---|
| **Claude Code** | ✅ primary target | Anthropic official CLI |
| Hermes Agent (NousResearch) | 🟡 partial | SKILL.md is portable; Hermes wrapper deferred |
| Codex CLI / Cursor / Gemini CLI / Goose | 🟡 SKILL.md only | agentskills.io standard adopted |

---

## ⚠️ Troubleshooting

### `nvm: command not found`

`source ~/.bashrc` may not work in all shells. **Close the terminal fully and open a new one**.

### `permission denied` on `install.sh`

```bash
chmod +x install.sh
./install.sh
```

Or just `bash install.sh`.

### tmux nesting error (`sessions should be nested with care`)

You already ran `claude` inside a tmux session. Use `Ctrl+B → c` to open a new window (the `ain` helper handles this automatically).

### git push rejected

Remote has new commits:

```bash
git pull --rebase
git push
```

### Discord bot pairing code expired

DM the bot again → it issues a fresh code.

### soul.md persona "ghost" (persona not loading)

If your bot's responses don't reflect the persona, the SessionStart hook is not reaching that session. The plugin registers it on install, and the hook deliberately stays silent unless `DISCORD_STATE_DIR` is set — so the two usual causes are a session started without that variable, or the plugin being disabled. To check the registration:

```
/thiscode:install-hooks
```

This verifies that `hooks/hooks.json` carries `bot-session-init.sh` and that the file is really there, and removes any duplicate left in `~/.claude/settings.json` by the older merge path — existing hooks of your own are preserved. An entry that merely shares a hook file name but shows no sign of belonging to ThisCode is never deleted: it is listed as a warning for you to review by hand.

### GraphRAG server won't start (vendor dependency + ~/.cache venv)

```bash
bash scripts/install-graphrag.sh --check     # python3 + vendor SoT + requirements + venv + server health
bash scripts/install-graphrag.sh --preflight # Python 3.10+ / disk 5GB+ / port 8400 / vendor SoT check
bash scripts/install-graphrag.sh --apply     # venv setup + pip install + nohup uvicorn
```

The `--apply` mode:
- venv location = `~/.cache/thiscode/graphrag/venv` (writable home cache)
- vendor SoT = `<thiscode>/vendor/graphrag/scripts/` (equivalent snapshot of vault SoT, 21 files)
- requirements = `vendor/graphrag/scripts/requirements.txt` (7 deps: networkx / louvain / pyyaml / fastapi / uvicorn / numpy / httpx)
- entry = `uvicorn search_server:app --host 127.0.0.1 --port 8400` (background nohup)
- log = `~/.cache/thiscode/graphrag/run/graphrag.log`

---

## 🔬 What's inside (advanced)

### The 3 hooks

- **`bot-session-init.sh`** (SessionStart) — auto-detects bot via `DISCORD_STATE_DIR` env var → injects soul.md + per-bot WD memory + common discipline
- **`discord-slash-cmd.sh`** (UserPromptSubmit) — if user prompt's first line is `/cmd`, forces Skill tool invocation
- **`regression-self-check.sh`** (UserPromptSubmit) — injects a 4-gate self-check table to refresh attention against regression patterns

### Skills (agentskills.io-standard)

- `init` — onboarding wizard (env detect + 8-Phase recommend)
- `bootstrap` — installer wizard helper
- `shared-memory` — 4-tier memory policy + Read-before-Edit
- `meetings` — 4-file meeting protocol + source-backed cross-check + Discord REST API threads
- `slack-bridge` — Slack bridge operations & troubleshooting (sender gates, bot-interop allowlist, live meeting canvas recipes)
- `codex-exec-bridge` — Codex CLI subprocess + `/tofu-at-codex` reference

### Codex CLI bridge

thiscode includes Codex CLI as a first-class bridge layer:

- `codex --version` and `codex exec --no-stream --model gpt-5.5` as subprocess
- Use cases: adversarial review, second-opinion code review, large-scale parallel research
- Verified via `/thiscode:codex-check`

### Custom Hybrid v1.0 agent spec

`schemas/agent-spec.json` defines a per-agent contract registry combining agentskills.io base + Hermes `provides_*` + thiscode classroom policy + dynamic gates + benchmark integration. v1.0 adds `tier: core` (init wizard) and `phases:` for km-at Mode R preflight workflow.

---

## 🤝 Contributing

This repo distills the author's (`treylom`) vault operations experience.

- PRs and issues welcome
- Debugging know-how contributions welcome
- Course learner feedback welcome

**Release discipline (2026-08-09)**: any skill/content change ships with a version
bump in **every surface the user-delivery path reads** — today that is
`.claude-plugin/plugin.json` **and** `.claude-plugin/marketplace.json`, in the same
commit. Without the bump, `claude plugin update` answers "already at the latest
version" and the fix never reaches installed users (measured 2026-08-09; the stale
`1.1.5` marketplace entry was the same failure). Surfaces NOT on that path, kept at
independent versions on purpose: `package.json` (npm-shape metadata, not published
to npm) and `gemini-extension.json` (separate Gemini CLI/OpenCode distribution
channel). If a new delivery surface appears, it joins the bump rule by the
criterion above, not by being on this list.

---

## 📄 License

MIT — free to use / modify / redistribute. Details: [LICENSE](LICENSE)

---

## 🔗 Related resources

- **gpakosz/.tmux** (oh-my-tmux): https://github.com/gpakosz/.tmux
- **agentskills.io** (SKILL.md open standard): https://agentskills.io
- **Anthropic Claude Code**: https://www.anthropic.com/claude-code
- **NousResearch/hermes-agent**: https://github.com/NousResearch/hermes-agent
- **OpenAI Codex CLI**: https://github.com/openai/codex

---

🇰🇷 **Korean version**: [README.ko.md](README.ko.md)
