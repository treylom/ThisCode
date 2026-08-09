---
description: Feature smoke test — verify shipped ThisCode features are wired (memory / tmux / discord-gate / graphrag / graphrag-bench / meeting / rules / hooks / install). Natural-language arg runs one; no arg runs all (except the heavy bench).
allowed-tools: Bash
disable-model-invocation: true
---

# /thiscode:test — feature smoke harness

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 문서 요약·소개 출력이나 "실행할까요?" 확인 질문으로 멈추지 말고 **아래 단계를 지금 즉시 실행**한다. (본문이 명시하는 인터뷰·AskUserQuestion 단계는 그 지점에서 그대로 수행 — 그 외 추가 확인 ❌)

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

Features: `memory`, `tmux`, `discord-gate`, `graphrag`, `graphrag-bench`, `meeting`, `rules`,
`hooks`, `install`.

## Run

```bash
# thiscode plugin 위치 detect — 낡은 사본 회피 (2026-08-10 핫픽스 B, 루돌프 실측
# 1536053876: 이전엔 cwd 상대 `node scripts/feature-test.mjs` 를 그대로 불러서, cwd 가
# 낡은 수동 clone(~/.claude/plugins/thiscode, discord-gate 항목 부재) 안이면 그 낡은
# 사본을 집어 7/7 을 냄 — 설치판(1.2.5, scripts/feature-test.mjs 직접 실행)은 8/8.
# install-hooks.md/create-bot.md 와 동일한 순서 probe 재사용(새 자동화 발명 ❌) — 단
# 실제 소비 파일(scripts/feature-test.mjs)의 실재로 판정, hooks/ 실재가 아니다.
PLUGIN_DIR=""
for _cand in \
  "$HOME/.claude/plugins/marketplaces/thiscode-marketplace" \
  "$HOME/.claude/plugins/thiscode" \
  "$HOME/.claude/plugins/cache/local/thiscode" \
  "$HOME/code/thiscode" \
  "$HOME"/.claude/plugins/cache/thiscode-marketplace/thiscode/*; do
  if [ -f "$_cand/scripts/feature-test.mjs" ]; then PLUGIN_DIR="$_cand"; break; fi
done

if [ -z "$PLUGIN_DIR" ]; then
  echo "❌ thiscode 의 scripts/feature-test.mjs 못 찾음 — plugin install (또는 git clone) 먼저"
  exit 1
fi

# node 우선, 없으면 bun 폴백 (Windows 신규 환경엔 node 가 없고 bun 만 있는 경우가 흔함)
if command -v node >/dev/null 2>&1; then
  node "$PLUGIN_DIR/scripts/feature-test.mjs" $ARGUMENTS
elif command -v bun >/dev/null 2>&1; then
  bun "$PLUGIN_DIR/scripts/feature-test.mjs" $ARGUMENTS
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
