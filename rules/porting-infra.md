# Rule: porting · deployment · infra

Trigger: porting a tool/skill/plugin to another platform; "deploy/push";
adding an MCP server; writing API code.

## 1. Check upstream before hand-rolling (critical)
- Before a hand-rolled workaround (symlinks etc.), check the upstream repo
  first: platform packaging (`.codex-plugin/`, `.cursor-plugin/`, …),
  `sync-to-*` scripts, AGENTS.md/GEMINI.md, the README multi-harness install
  matrix. Upstream has usually already solved it. Label provenance
  (file:line / source) on what you find.

- **Absence from a support/compatibility list ≠ "cannot be used" (2026-09-01)**:
  a docs list is a snapshot of what marketing/documentation covered, not a
  capability boundary. Drop one layer down and measure the protocol/executable
  surface directly once before declaring "unsupported".

## 2. Deploy sync
- On "deploy/push", sync **all** companion repos that must stay in lockstep,
  not just one.
- Before any push: secret/PII scan the diff with a **raw (unfiltered)** tool
  (a token-optimizer-filtered grep can blank/mangle matches — see
  source-fact.md §2). A public-repo change is the user's authority domain
  (autonomy.md §1) — confirm unless under a standing go.
- Dual-platform packaging: ship one repo with **both** manifests — Claude Code
  (`.claude-plugin/`) and Codex/ChatGPT (`.codex-plugin/plugin.json` +
  `.agents/plugins/marketplace.json` for a catalog repo). Additive only —
  never move or rename existing skill/guide paths that installed users
  already reference. Note: ChatGPT desktop (Work) marketplace registration
  additionally requires the `.claude-plugin/{marketplace.json, plugin.json}`
  PAIR at repo root (empirically verified 2026-07: `.codex-plugin` alone is
  rejected), and Codex CLI plugin names only allow ASCII letters, digits, `_`, `-`
  (dots included in the rejects) — use `name-2-0` style.
- When a public-repo push changes **model-lineup or coverage wording** in the
  README/skills, update the repo's About (description/topics) in the same
  session (`gh repo edit --description`) — About is the search/first-impression
  surface; letting it lag the README is stale advertising.
- Rule / operating-principle changes in the source repo sync to this
  deploy bundle's rules/ **at session-end** — else the bundle drifts
  from the source rules (a standing operator directive).
- **File-tree syncs into a consumer store use one guarded entrypoint.** Strip the source project-root prefix from the destination mapping and reject any destination that repeats that project-root segment (the classic nested-shadow-tree failure). After the sync, verify that no prefixed shadow root exists; if one does, stop and report it without auto-deleting or overwriting. The operator performing the sync runs this postcondition in the same turn. Case-scoped; adapt the concrete wrapper/path to the deployment.

- **User-facing copy: grep for internal/course jargon before push (2026-09-01)**:
  plugin READMEs, command help and onboarding copy leak internal names (course
  numbering, in-house bot/channel names) easily; one grep line before push, by
  the pushing agent, replaces them with public vocabulary.

## 3. MCP servers
- Before adding: list current MCPs. After adding: health-check. Remove on
  connect failure immediately.

## 4. API code
- When writing API code, consult an up-to-date docs source first; copy a known
  example. Use the exact model id from the agent's spec — never a guessed /
  knowledge-cutoff model name.

▶ Fill in: your companion-repo list + sync targets; your secret-scan command;
your MCP list/health commands; your API docs source.
