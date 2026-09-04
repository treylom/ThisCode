# Hermes plugin — status: partial / deferred

> Decision: maintainer, 2026-05-16, option ② (redesign to current structure +
> document deferred — do **not** reconstruct the missing dispatchers).

## TL;DR

The `hermes-plugin/` registers thiscode tools into a Hermes Agent host. Its
**programmatic search/ingest path is deferred**. Use the Claude Code path
(`/search`, `/thiscode:km`, or the skills via an LLM agent) for real work.

## What works (active)

| Piece | State |
|---|---|
| Plugin registration (`__init__.py`) | ✅ tools/commands/hook register cleanly |
| `session_start_drift_check` | ✅ real — shells out to `scripts/km-version.sh` (exists) |
| `plugin.yaml` metadata / agent-spec aggregation | ✅ |

## What is deferred (and why)

| Piece | State | Why |
|---|---|---|
| `handle_search` / `cmd_search` (`claude_discode_search`) | ⏸️ deferred | needs an executable search dispatcher, which is not bundled |
| `handle_ingest` / `cmd_km` (`claude_discode_ingest`) | ⏸️ deferred | needs an executable ingest dispatcher, which is not bundled |

**Root cause (verified 2026-05-16, independent cross-validation):** thiscode skills
are **LLM-instruction documents** (`SKILL.md` + `references/*.md`), not
executable shell dispatchers. The literate-bash `*.md.sh` dispatchers the
Hermes handlers shell out to were never vendored to the public repo (they
existed only in a private workspace). A programmatic plugin cannot
byte-identically "run" an LLM-instruction skill, so reconstructing the
dispatchers from a guess was explicitly rejected (reconstruction risk).

## Current behavior (honest, non-failing)

- `handle_search` / `handle_ingest`: if the dispatcher file is absent they
  return a structured **`{"status":"deferred", ...}`** JSON pointing here and
  at the Claude Code path. They never raise (Hermes contract) and never fake a
  result.
- The four shell tests that exercised the dispatchers were removed in 1.4.0
  together with the skills they pointed at — they could only ever SKIP, so
  CI is honest, not red, and not falsely green.

## Supported path instead

Use thiscode through **Claude Code** (or any LLM agent that reads `SKILL.md`):

- Install the km plugin (`claude plugin marketplace add treylom/tofukyung-plugins`
  + `claude plugin install km@tofukyung-plugins`) and use its search and
  knowledge commands — `/km:search` for 4-Tier vault search.

## How to un-defer (future)

To make the Hermes programmatic path real, add executable dispatchers at the
two paths above that implement the 4-Tier search / km-lite extract contracts
(`contracts/search-fallback-4tier.md`, `contracts/km-*.md`). Once present, the
handlers' `*.exists()` guard automatically resumes the normal `_run(...)` path
and the four tests stop skipping — no further code change required.
