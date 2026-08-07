# ATTRIBUTIONS

thiscode v2.3 가 의존하는 모든 외부 패키지 / repo 의 출처 / license / version pin.

> 본 매트릭스 = spec doc `docs/superpowers/specs/2026-05-13-thiscode-v2.3-dependency-packaging-design.md` §5 동등.
> Phase 1 (~30 min) + Phase 2 (~4 min line-by-line) GPT-5.5 codex 검수 반영.
> license cross-compatibility = MIT + Apache-2.0 + BSD-3-Clause + Unlicense + CC-BY-4.0 모두 permissive, copyleft (GPL/LGPL) zero — cross-compatible.

## thiscode 본 repo

| Name | Source | License | Version |
|------|--------|---------|---------|
| thiscode | github.com/treylom/ThisCode | MIT (see `LICENSE`) | v2.3.0 |

## Plugin (1)

| Name | Source | License | Version | Install method |
|------|--------|---------|---------|----------------|
| superpowers | github.com/anthropics/claude-plugins-official | MIT | 5.1.0 | Claude Code plugin manager (`claude plugin install superpowers@claude-plugins-official`) |

## Spec doc (2 — vendored 본문)

| Name | Source | License | Version | Vendored at |
|------|--------|---------|---------|-------------|
| agentskills | github.com/agentskills/agentskills | Apache-2.0 (code) + CC-BY-4.0 (docs) dual | latest 2026-05-13 | `vendor/agentskills/SKILL-SPEC.md` |
| hermes-agent | github.com/NousResearch/hermes-agent | MIT | latest 2026-05-13 | `vendor/hermes/HERMES-SPEC.md` |

> agentskills repo = SKILL.md open standard 의 정확 primary SoT (18.5k stars). `agentskills-io/agent-skills-in-action` 는 Manning book companion (별도 repo, 본 spec 의 도서 예제). vendored 본문 = docs portion → CC-BY-4.0 attribution 의무.

## External tools — required (5 — base)

| Name | Source | License | Install method |
|------|--------|---------|----------------|
| ripgrep | github.com/BurntSushi/ripgrep | Unlicense + MIT dual | `install-ripgrep.sh` (brew / apt / dnf / apk) |
| networkx | github.com/networkx/networkx | BSD-3-Clause | `install-graphrag.sh` (pip) |
| python-louvain | github.com/taynaud/python-louvain | BSD-3-Clause | `install-graphrag.sh` (pip) |
| pyyaml | github.com/yaml/pyyaml | MIT | `install-graphrag.sh` (pip) |
| fastapi | github.com/tiangolo/fastapi | MIT | `install-graphrag.sh` (pip) |

## External tools — required (3 — v0.2 audit 추가)

| Name | Source | License | Install method |
|------|--------|---------|----------------|
| uvicorn | github.com/encode/uvicorn | BSD-3-Clause | `install-graphrag.sh` (pip) |
| numpy | github.com/numpy/numpy | BSD-3-Clause (with bundled dependencies under additional permissive licenses — see PyPI metadata for current SPDX compound expression) | `install-graphrag.sh` (pip, `embedding_index.py:21` 의존) |
| httpx | github.com/encode/httpx | BSD-3-Clause | `install-graphrag.sh` (pip, `graph_search.py:174` 의존) |

## External tools — optional GUI guide (1)

| Name | Source | License | Install method |
|------|--------|---------|----------------|
| Obsidian CLI | obsidian.md (3-binary detect) | Obsidian proprietary GUI | `install-obsidian-cli.sh` (브라우저 download 안내, WSL = Windows side install) |

## Optional Dense channel (3 — 사용자 confirm 1회)

| Name | Source | License | Install method |
|------|--------|---------|----------------|
| torch | github.com/pytorch/pytorch | BSD-3-Clause | `install-dense-embedding.sh` (pip, ~600MB) |
| transformers | github.com/huggingface/transformers | Apache-2.0 | `install-dense-embedding.sh` (pip, ~500MB) |
| sentence-transformers | github.com/UKPLab/sentence-transformers | Apache-2.0 | `install-dense-embedding.sh` (pip) |

## Vendored Python runtime (thiscode/vendor/graphrag/)

GraphRAG core 26 file (`.py` 23 + `.sh` 2 + `requirements.txt` 1) + method 문서 1 = 추적 27. obsidian-ai-vault `.team-os/graphrag/scripts/` 와 동등 vendor 박제.

- **출처**: 동일 코드가 **공개 플러그인 레포 [treylom/tofugraph](https://github.com/treylom/tofugraph)** 로도 배포된다(`engine/scripts/` 13 file = 본 vendor 의 **부분집합** — 본 vendor 가 상위집합이며 benchmark·test 계열 11 file 을 더 갖는다). 원본 SoT = 비공개 vault `.team-os/graphrag/scripts/`.
- **License: MIT** (treylom own — thiscode 본 repo 와 동일). `tofugraph` README 의 License 절도 MIT 로 동일 선언.
- Update 정책: pin version (vault SoT 변경 시 manual sync). ⚠️ **판본이 셋(vault SoT · tofugraph · 본 vendor)이므로 동기화 시 세 곳 다 확인** — 강의 Part4 는 수강생에게 `tofugraph@tofukyung-plugins` 마켓 설치를 안내하므로, 수강생 손에 가는 것은 tofugraph 쪽이다.

## License compatibility 검증 (Phase 1 + Phase 2 GPT-5.5)

본 매트릭스 license set:
- MIT (thiscode, superpowers, hermes-agent, pyyaml, fastapi)
- Apache-2.0 (agentskills code, transformers, sentence-transformers)
- CC-BY-4.0 (agentskills docs — vendored spec 본문)
- BSD-3-Clause (networkx, python-louvain, uvicorn, numpy, httpx, torch)
- Unlicense + MIT (ripgrep)
- Obsidian proprietary GUI (안내만 — vendor 없음)

**cross-compatibility:** MIT + Apache-2.0 + BSD-3-Clause + Unlicense + CC-BY-4.0 모두 permissive license. copyleft (GPL / LGPL) zero. thiscode 본 license (MIT) 와 호환. CC-BY-4.0 안 attribution 의무 = vendor/agentskills/SKILL-SPEC.md + vendor/agentskills/LICENSE 안 명시.

---

본 매트릭스 변경 시: spec doc §5 동시 update. CI smoke test 안 `pip install -r vendor/graphrag/scripts/requirements.txt` 자동 검증.

## Vendored Slack bridge (vendor/claude-channel-server/)

`claude-channel-server` = Claude Code 공식 `claude/channel` MCP 프로토콜의 Slack 브리지 구현(`server.ts`+`mcp.ts`, `src/*.ts` 7 file). ThisCode로 Slack을 연결하려는 모든 사용자에게 필요해 vendor 동봉(2026-08-06 결정 ⓐ, [slack-bridge/SKILL.md](skills/slack-bridge/SKILL.md) 참고).

- 출처: 비공개 저장소 `slack-agent-bridge/claude-channel-server`(treylom 소유, 2026-08-06 snapshot)
- **License: MIT** — 저작권자(treylom) 결정으로 thiscode 본 repo와 동일한 MIT로 통일(2026-08-06 승인). `vendor/claude-channel-server/LICENSE` = thiscode 루트 `LICENSE`와 바이트 동일, `package.json`에 `"license": "MIT"` 명시(구 `"private": true`는 배포 대상이므로 제거).
- 빌드 산출물(`dist/`)은 동봉하지 않는다 — 소스↔빌드본 drift 방지. `slack:configure` Step 0이 설치·빌드를 자동 수행한다(사람 관문 아님).
- Update 정책: pin snapshot (upstream `slack-agent-bridge` 변경 시 manual sync)

## Vendored vault-search MCP (vendor/vault-search-mcp/)

`vault-search-mcp` = vault GraphRAG 검색을 MCP 서버로 노출하는 stdio/HTTP 브리지(`src/index.ts`·`auth.ts`·`http.ts`, 추적 13 file). `install-vault-search.sh` 가 설치 시점에 빌드한다(`dist/` 는 `.gitignore` 제외 — 소스↔빌드본 drift 방지).

- 출처: treylom own (thiscode 와 동일 저작권자)
- **License: MIT** (2026-08-06 저작권자 결정 — `LICENSE` 파일 + `package.json` `"license": "MIT"`, 구 `"private": true` 제거)
- Update 정책: pin snapshot (manual sync)

> 본 항목은 2026-08-06 이전 **매트릭스에서 누락**돼 있었다(vendor 에는 있는데 attribution 0건). 「전체 목록」 주장이 실제 커버리지보다 넓었던 자리 — 글재경 r3 ⓓ 발견.

## Vendored prompt skill (skills/prompt/)

`/prompt` 생태계 = 공개 upstream **github.com/treylom/prompt-engineering-skills** (MIT) vendor 박제.

- 출처: github.com/treylom/prompt-engineering-skills (public, MIT — see skills/prompt/LICENSE)
- 반입: commands/prompt.md→references/prompt-generator.md, skills/prompt-engineering-guide.md, examples/, instructions/. **commands/prompt-sync.md 제외** (메인테이너 개인 배포 스크립트·경로, 배포자 무관)
- Context-Engineering 기반: Muratcan Koylan, Agent-Skills-for-Context-Engineering
- Update 정책: pin (upstream 변경 시 manual re-vendor + PII 재검증)
