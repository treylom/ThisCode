# Shell-test registration policy

The repository currently tracks 39 `tests/**/*.sh` files. `npm test` discovers
only `tests/**/*.test.mjs`, so shell tests are registered through the explicit
allowlist in `scripts/run-shell-tests.mjs` and the `validate-agents` workflow.
The runner intentionally does not recurse over `tests/`: several shell tests
inspect host state, user configuration, or live services.

## CI allowlist

The following 25 files are safe to run in a disposable CI checkout. They use
fixed repository fixtures or temporary directories and do not contact a live
vault, MCP, GraphRAG server, Obsidian app, or user service. They can still need
`bash`, Node, Python, `jq`, `yq`, `ajv`, `ajv-formats`, or `rg`; the workflow
installs those prerequisites.

```text
tests/agents/test-all-yamls.sh
tests/agents/test-hermes-runtime-manifest.sh
tests/agents/test-index-roundtrip.sh
tests/agents/test-plugin-sync.sh
tests/agents/test-plugin-v2.sh
tests/agents/test-router-yaml.sh
tests/agents/test-schema-validation.sh
tests/benchmark/test-fixtures-shape.sh
tests/benchmark/test-tier-label-v2.sh
tests/benchmark/test-tier-swap.sh
tests/benchmark/test-tier1-skip.sh
tests/benchmark/test-tier3-syntax.sh
tests/benchmark/test-tier4.sh
tests/docs/test-glossary.sh
tests/docs/test-manual-v2.sh
tests/init/test-commands-init.sh
tests/init/test-contract-tier-order.sh
tests/init/test-phase-recommend.sh
tests/init/test-readme-vault-first.sh
tests/init/test-setup-beginner-wizard.sh
tests/init/test-skill-init.sh
tests/push/test-classify-push-diff.sh
tests/router/test-route-model.sh
tests/test-install-vault-search.sh
tests/test-km-version.sh
```

`test-index-roundtrip.sh` regenerates `agents.yaml`, and the benchmark Tier 1
skip/Tier 4 checks write ignored result fixtures. Both are safe only because
CI runs in a disposable checkout; neither is a reason to recursively execute
the suite in a user's worktree.

## Intentional exclusions

| File | Why it is excluded from the hermetic runner | Intended surface |
|---|---|---|
| `tests/benchmark/test-report-generator.sh` | Runs the four-tier benchmark; Tier 2 reads `$HOME/.config/claude`, and Tier 3 may invoke an installed Obsidian CLI. | Manual or isolated benchmark job. |
| `tests/benchmark/test-tier2-3-shape.sh` | Invokes the same host-configured Tier 2/Tier 3 runners and may call a live CLI. | Manual or dedicated environment with HOME/PATH isolation. |
| `tests/dogfood/run-all.sh` | Writes a dated host report and orchestrates the GraphRAG scenario. | Docker/manual dogfood. |
| `tests/dogfood/scenario-2-mcp.sh` | Temporary HOME is controlled, but PATH is not; the installer can detect and invoke a host `claude` CLI. | Docker/manual; isolate PATH before any CI use. |
| `tests/dogfood/scenario-3-graphrag.sh` | Runs GraphRAG installer health checks against host Python/vendor/port state. | Manual or dedicated host-smoke job. |
| `tests/init/test-env-detect.sh` | `--detect-only` scans the host vault, tools, OS, and resources. | Manual or a future fixture-backed test. |
| `tests/init/test-graphrag-preflight.sh` | Checks host Python version, free disk, RAM, port 8400, and vendor state. | Manual/dedicated host-smoke. |
| `tests/init/test-healthcheck-phase.sh` | Runs the environment healthcheck rather than a fixed fixture. | Manual/dedicated environment. |
| `tests/init/test-install-obsidian-json.sh` | Detects host Obsidian binaries/app paths and OS. | Manual or OS-specific host-smoke. |
| `tests/init/test-non-interactive.sh` | Non-interactive mode still performs host vault/tool/resource detection; its override covers only one path. | Manual until complete fixture injection exists. |
| `tests/init/test-setup-beginner-typ.sh` | Content check is static, but PDF-vs-Typst mtime validation uses BSD/GNU-specific `stat` behavior. | Platform-aware manual/CI lane, not the portable allowlist. |
| `tests/init/test-vault-search-note-count.sh` | `VAULT="$TMP"` is passed after `--recommend-only` as an argument, while the installer expects the `VAULT` environment variable; it can inspect the default host vault. | Manual until invocation is corrected and fixture-controlled. |
| `tests/test-install-graphrag.sh` | Read-only `--check` probes vendored state and localhost:8400; it is host-smoke, not hermetic. | Existing labelled CI host-smoke (`validate-agents.yml:90`). |
| `tests/test-install-obsidian-cli.sh` | Read-only detection checks OS, PATH, `/Applications`, and home app paths. | Existing labelled CI host-smoke (`validate-agents.yml:91`). |

The two root installer host-smoke tests remain in their existing workflow steps;
their presence there does not make them part of the hermetic allowlist. No
excluded test is executed by `scripts/run-shell-tests.mjs`.
