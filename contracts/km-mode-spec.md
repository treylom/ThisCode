---
contract: km-mode-spec
version: 0.1.0
date: 2026-05-13
---

# KM Mode Migration Pointer

ThisCode does not provide knowledge management or vault search workflows. The
km plugin owns the current ingestion, organization, graph, and search behavior;
consult its documentation for the supported modes and commands. This file is a
compatibility pointer for older references, not an implementation supplied by
ThisCode or by `/thiscode:km`.

Use the km plugin's current entry points:

- `/km:knowledge-manager` for knowledge collection and organization.
- `/km:search` for the search fallback dispatcher.
- `/km:setup` for km storage, integrations, and configuration.

ThisCode continues to provide optional local search-tool installer scripts in
`scripts/install-*.sh`. Those scripts install local engines; they do not provide
the km plugin's knowledge workflows or search dispatcher.
