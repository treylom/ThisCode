---
description: Feature smoke test — verify shipped ThisCode features are wired (memory / tmux / graphrag / graphrag-bench / meeting / rules / hooks / install). Natural-language arg runs one; no arg runs all (except the heavy bench).
allowed-tools: Bash
disable-model-invocation: true
---

# /thiscode:test — feature smoke harness

> This is **not** the dev unit suite (`npm test`). It proves the *shipped
> features* are wired, with graceful **SKIP** when an optional runtime
> dependency is absent — only a real breakage is **FAIL**.

$ARGUMENTS

---

## What it does

| Input | Behaviour |
|---|---|
| `/thiscode:test` (no arg) | Sequential smoke of **all** features **except** `graphrag-bench` (heavy) |
| `/thiscode:test <natural language>` | Fuzzy-match **one** feature and run only it (e.g. `/thiscode:test 메모리`, `/thiscode:test check the meeting protocol`) |
| `/thiscode:test graphrag-bench` | The heavy GraphRAG benchmark only (separately runnable, by design) |
| `/thiscode:test all` (or `--bench`) | Everything **including** `graphrag-bench` |

Features: `memory`, `tmux`, `graphrag`, `graphrag-bench`, `meeting`, `rules`,
`hooks`, `install`.

## Run

```bash
# node 우선, 없으면 bun 폴백 (Windows 신규 환경엔 node 가 없고 bun 만 있는 경우가 흔함)
if command -v node >/dev/null 2>&1; then
  node scripts/feature-test.mjs $ARGUMENTS
elif command -v bun >/dev/null 2>&1; then
  bun scripts/feature-test.mjs $ARGUMENTS
else
  echo "❌ node/bun 둘 다 없음 — windows-setup.ps1(또는 bun.sh) 로 bun 설치 후 재시도"
fi
```

- Exit `0` = no FAIL (SKIP never fails the run).
- Exit `1` = at least one feature FAIL.
- Exit `2` = the natural-language arg matched no known feature (the message
  lists the known feature ids).

## Notes

- The harness is **deterministic / idempotent** (filesystem + binary probes
  only). It is test code, so it is safe — and expected — to run repeatedly;
  multi-run stability is part of its contract and is asserted in
  `tests/feature/feature-test-harness.test.mjs`.
- A missing optional dependency (e.g. tmux not installed, graphrag runtime not
  yet installed) is reported as **SKIP**, not FAIL — the feature is *shipped*
  even if a runtime is not present on this machine.
