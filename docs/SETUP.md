# SETUP — thiscode (개발자 / 일반 사용자)

5 단계, 매 step 검증 명령 + troubleshooting 1-2 line. **초보자는 [SETUP-BEGINNER.md](SETUP-BEGINNER.md) 권장**.

## 0. AI에게 설치 맡기기

아래 문장을 Claude Code 또는 Codex에 붙여 넣으면, AI가 이 문서와 스크립트를
함께 따라가며 설치를 진행합니다. `prompt`(AI에게 주는 작업 지시문)는
ThisCode/ThisCodex의 `/prompt` 원칙처럼 목표, 확인 조건, 중단 조건을 한 번에
담습니다.

```text
https://github.com/treylom/ThisCode 를 설치해줘. README.md와 docs/SETUP.md를 먼저 읽고, 각 단계마다 실행할 명령을 말한 뒤 실행해. 토큰/자격증명, ~/.claude 설정, 시스템 패키지 설치는 실행 전에 나에게 확인해. 끝나면 bash ~/.claude/plugins/thiscode/scripts/healthcheck.sh 를 실행하고 결과를 요약해.
```

스크립트로 직접 시작할 때:

```bash
mkdir -p ~/.claude/plugins
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode
bash ~/.claude/plugins/thiscode/scripts/claude-discode-init.sh
```

## 1. Prereq (5분)

```bash
node --version          # 검증: v18.x.x 이상
jq --version            # 검증: jq-1.6+
git --version           # 검증: 2.30+
claude --version 2>/dev/null  # (선택) Claude Code CLI
```

troubleshooting: 미설치 시 https://nodejs.org / `brew install jq` / `brew install git`

## 2. Plugin install (2분)

```bash
mkdir -p ~/.claude/plugins
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode
ls ~/.claude/plugins/thiscode/.claude-plugin   # 검증: 출력 있음
```

advanced (1-line installer): `curl -fsSL https://raw.githubusercontent.com/treylom/ThisCode/main/install.sh | bash`

troubleshooting: `~/.claude/plugins/` 디렉토리 없으면 `mkdir -p ~/.claude/plugins` 먼저

## 2.5 Codex 에서 지식관리 쓰기 (Codex 봇 사용자만)

ThisCode 1.4.0 부터 지식관리·vault 검색 스킬은 이 레포에 들어 있지 않습니다 — km 플러그인이
제공합니다(`claude plugin marketplace add treylom/tofukyung-plugins` +
`claude plugin install km@tofukyung-plugins`). Codex 쪽 사용법은 그 플러그인 문서를 따릅니다.

1.4.0 부터 ThisCode 의 Codex 스킬 내보내기 목록은 비어 있습니다. 과거 목록은 KM 계열뿐이었고,
그 기능은 Codex를 직접 지원하는 km 플러그인으로 옮겨 갔으므로 ThisCode에서 내보낼 항목이 없습니다.
기본 check 모드(`--check`는 별도 분기로 파싱되지 않음)는 빈 목록이면 "nothing to export"를 출력합니다.
`--apply`는 비대화형 실행에서 `--yes` 또는 `--answers=...` 동의가 필요하며, `harness` 답변이
`codex` 또는 `both`이고 `codex_skill_layer`가 `repo`가 아닐 때에만 같은 빈 내보내기 메시지를 출력합니다.

```bash
node bin/thiscode.mjs --check       # --check는 기본 check 모드 실행(무변경, nothing to export)
node bin/thiscode.mjs --apply --yes # 비대화형 apply 동의; Codex export 조건을 충족할 때만 같은 메시지 출력
```

## 3. km 플러그인 설정과 선택 검색 도구

`/km:setup`은 km 저장 위치·Playwright/Obsidian MCP·`km-config.json`·vault 경로와 구조 문서를 구성합니다. 검색 Tier 설치 명령은 아닙니다.

```text
/km:setup
```

로컬 검색 도구가 필요하면 ThisCode의 아래 스크립트 중 필요한 Tier만 선택해 실행합니다.

```bash
bash ~/.claude/plugins/thiscode/scripts/install-ripgrep.sh --apply
bash ~/.claude/plugins/thiscode/scripts/install-obsidian-cli.sh
bash ~/.claude/plugins/thiscode/scripts/install-vault-search.sh --apply
bash ~/.claude/plugins/thiscode/scripts/install-graphrag.sh --apply
```

검색 fallback 실행은 km 플러그인의 `/km:search`, km 플러그인 설정 생성·재설정은 `/km:setup`이 담당합니다.

## 검증 (전체)

```bash
bash ~/.claude/plugins/thiscode/scripts/healthcheck.sh
```

예상 출력 (환경에 따라 각 단계의 상태가 달라집니다):

```
thiscode healthcheck v2.3 — Phase progress
─────────────────────────────────
✓ Phase 0 superpowers (plugin)       : OK
✓ Phase 1 ripgrep (Tier 4)           : OK
○ Phase 2 obsidian-cli (Tier 2)      : NOT YET
○ Phase 3 vault-search MCP (Tier 3)  : NOT YET
○ Phase 4 GraphRAG (Tier 1)          : NOT YET
○ Phase 5 Dense embedding (4-channel): NOT YET
─────────────────────────────────
Summary: 2 OK, 4 NOT YET (all required passed) ✅
```

Exit code: `0` = all phases OK / `1` = required FAIL / `2` = optional phase가 아직 준비되지 않음.

## 사용

```
/thiscode:km                     # km 플러그인 설치 안내 (검색·지식관리)
/thiscode:init                   # ThisCode 환경 감지·설정 인터뷰
/thiscode:setup                  # ThisCode 봇 하네스 재설정
/km:setup                        # km 저장 위치·MCP·설정 구성
/km:search "your query"          # km 플러그인 설치 후 검색 fallback 자동
```

## 벤치마크 (선택)

```bash
cd ~/.claude/plugins/thiscode
VAULT=./sample-vault BENCHMARK_SKIP_TIER1=1 bash benchmark/runners/run-all.sh
python3 benchmark/report-generator.py --print-only
```

자기 vault 측정: `VAULT=~/path/to/vault ...` — 단 `benchmark/fixtures/queries.yaml` 의 `expected_hits` 는 본인 vault 에 맞게 수정 필요 (자세한 건 [docs/BENCHMARK.md](BENCHMARK.md)).
