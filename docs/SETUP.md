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
그 기능은 km 플러그인이 Codex 를 직접 지원하므로 ThisCode 에서 내보낼 항목이 없습니다.
`--check` 와 `--apply` 는 이 상태를 "nothing to export"로 알립니다.

```bash
node bin/thiscode.mjs --check    # 미리보기(무변경, nothing to export)
node bin/thiscode.mjs --apply    # 내보낼 항목 없음 (harness=codex/both 선택 시에도 동일)
```

## 3. Tier 2 — vault-search MCP (5분, 권장)

```bash
bash ~/.claude/plugins/thiscode/scripts/install-vault-search.sh --apply
claude mcp list | grep vault-search   # 검증: vault-search 항목 출력
```

Claude Code 재시작 필요. troubleshooting: `npm install` 실패 시 `nvm use 18`

## 4. Tier 3 — obsidian-cli (3분, Obsidian 사용자만)

```bash
bash ~/.claude/plugins/thiscode/scripts/install-obsidian-cli.sh
which obsidian-cli      # 검증: path 출력
```

Obsidian 미사용 시 skip.

## 5. Tier 1 — GraphRAG (20-30분, advanced)

Python 3.10+, Docker (선택) 필요.

```bash
bash ~/.claude/plugins/thiscode/scripts/install-graphrag.sh --apply
curl localhost:8400/health   # 검증: {"status":"ok"}
```

첫 indexing 시간 ~15분 (vault 크기 의존). troubleshooting: port 8400 충돌 시 `GRAPHRAG_PORT=8401 bash scripts/...`

## 검증 (전체)

```bash
bash ~/.claude/plugins/thiscode/scripts/healthcheck.sh
```

예상 출력:

```
thiscode healthcheck v1.0
─────────────────────────────────
✓ Tier 4 (ripgrep)  : OK
✓ Tier 3 (MCP)      : OK
✓ Tier 2 (CLI)      : OK
✓ Tier 1 (GraphRAG) : OK
─────────────────────────────────
all required checks passed ✅
```

Exit code: `0` = all required OK / `1` = required FAIL / `2` = intentional SKIP only (예: Tier 1 안 깔음)

## 사용

```
/thiscode:km                     # km 플러그인 설치 안내 (검색·지식관리)
/thiscode:setup                  # 재설정 (Tier 추가/제거)
/km:search "your query"          # km 플러그인 설치 후 4-Tier fallback 자동
```

## 벤치마크 (선택)

```bash
cd ~/.claude/plugins/thiscode
VAULT=./sample-vault BENCHMARK_SKIP_TIER1=1 bash benchmark/runners/run-all.sh
python3 benchmark/report-generator.py --print-only
```

자기 vault 측정: `VAULT=~/path/to/vault ...` — 단 `benchmark/fixtures/queries.yaml` 의 `expected_hits` 는 본인 vault 에 맞게 수정 필요 (자세한 건 [docs/BENCHMARK.md](BENCHMARK.md)).
