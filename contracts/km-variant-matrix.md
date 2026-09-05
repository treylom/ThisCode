---
contract: km-variant-matrix
version: 0.2.0
date: 2026-09-05
---

# KM Variant Migration Pointer

ThisCode no longer implements KM modes or variant selection. The old variant
matrix is retained here only as a migration pointer for installations that still
refer to this contract; it is not a ThisCode command surface.
There is no local `--variant` or mode-selection interface to maintain here.

The km plugin is the current owner of knowledge management and vault search:

- `/km:knowledge-manager` handles knowledge collection and organization.
- `/km:search` runs the search fallback dispatcher.
- `/km:setup` configures the km plugin and its integrations.

ThisCode's `/thiscode:km` command points users to those km plugin commands. The
local search-tool installers remain in ThisCode (`scripts/install-*.sh`); they
install optional engines but do not provide the km workflows or dispatcher.
