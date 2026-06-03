# Rule: porting · deployment · infra

Trigger: porting a tool/skill/plugin to another platform; "deploy/push";
adding an MCP server; writing API code.

## 1. Check upstream before hand-rolling (critical)
- Before a hand-rolled workaround (symlinks etc.), check the upstream repo
  first: platform packaging (`.codex-plugin/`, `.cursor-plugin/`, …),
  `sync-to-*` scripts, AGENTS.md/GEMINI.md, the README multi-harness install
  matrix. Upstream has usually already solved it. Label provenance
  (file:line / source) on what you find.

## 2. Deploy sync
- On "deploy/push", sync **all** companion repos that must stay in lockstep,
  not just one.
- Before any push: secret/PII scan the diff with a **raw (unfiltered)** tool
  (a token-optimizer-filtered grep can blank/mangle matches — see
  source-fact.md §2). A public-repo change is the user's authority domain
  (autonomy.md §1) — confirm unless under a standing go.
- Rule / operating-principle changes in the source repo sync to this
  deploy bundle's rules/ **at session-end** — else the bundle drifts
  from the source rules (a standing operator directive).

## 3. MCP servers
- Before adding: list current MCPs. After adding: health-check. Remove on
  connect failure immediately.

## 4. API code
- When writing API code, consult an up-to-date docs source first; copy a known
  example. Use the exact model id from the agent's spec — never a guessed /
  knowledge-cutoff model name.

▶ Fill in: your companion-repo list + sync targets; your secret-scan command;
your MCP list/health commands; your API docs source.
