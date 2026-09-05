# 🚀 thiscode 처음이세요? 5단계로 끝납니다

> 이 가이드는 컴퓨터 기초만 있으면 따라할 수 있습니다.
> 막히면 각 step 의 "❓ 실패 시" 박스 참고. 그래도 안 되면 마지막 단계에서 GitHub Issue 등록 (1분).

## 먼저: AI에게 이렇게 말하세요

Claude Code 또는 Codex에 아래 문장을 그대로 붙여 넣으면 됩니다.

```text
https://github.com/treylom/ThisCode 에 있는 README.ko.md와 docs/SETUP-BEGINNER.md를 읽고, 단계별로 설치를 도와줘. 내가 복사해야 할 명령은 한 번에 하나씩 보여주고, 토큰/자격증명이나 시스템 패키지 설치 전에는 꼭 확인 질문을 해줘. 마지막에는 healthcheck 검증까지 실행해줘.
```

직접 터미널에서 시작하려면 이 세 줄입니다:

```bash
mkdir -p ~/.claude/plugins
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode
bash ~/.claude/plugins/thiscode/scripts/claude-discode-init.sh
```

## 0단계: wizard 진입 (v2.1 추천)

가장 쉬운 방법은 `thiscode init` wizard — vault / 도구 / 자원 자동 감지 + 8 Phase 추천.

```bash
bash ~/.claude/plugins/thiscode/scripts/claude-discode-init.sh
```

wizard 가 물어보는 항목:
- 어떤 Tier 의 검색 도구를 install? (현재 가능 / 권장 / 나중 3 단계 표시)
- GraphRAG install? (500+ 노트 권장, 단 옵션 언제나)
- Mode R preflight? (2000+ 노트 권장, read-only 진단만)

자세한 단계별 install 은 본 문서 1~5 단계 참고. (wizard 진입 안 한 사용자 위함)

---

## 1단계: 시작 전 환경 점검 (2분)

먼저 컴퓨터에 뭐가 깔려있는지 확인합니다. 아래 명령을 터미널에 한 줄씩 복사 + 붙여넣기 + Enter.

```bash
node --version
```

**✅ 성공 모습:** `v18.17.0` 같은 숫자가 보이면 OK
**❌ 실패 시:** "command not found" 가 나오면 → https://nodejs.org 에서 LTS 버전 (v18 또는 v20) 설치 후 터미널 재시작

```bash
jq --version
```

**✅ 성공 모습:** `jq-1.6` 같은 출력
**❌ 실패 시:** macOS = `brew install jq` / Ubuntu/WSL = `sudo apt install jq`

```bash
git --version
```

**✅ 성공 모습:** `git version 2.x.x`
**❌ 실패 시:** macOS = `xcode-select --install` / Ubuntu/WSL = `sudo apt install git`

---

## 1단계: 플러그인 설치 (2분)

```bash
mkdir -p ~/.claude/plugins
git clone https://github.com/treylom/ThisCode ~/.claude/plugins/thiscode
```

**✅ 성공 모습:**

```
Cloning into '/Users/.../thiscode'...
remote: Enumerating objects: ...
Receiving objects: 100% (...), done.
```

**❌ 실패 시:**

- "Permission denied" → `mkdir ~/.claude/plugins` 권한 확인
- "already exists" → 이미 설치됨. `cd ~/.claude/plugins/thiscode && git pull` 로 update

---

## 2단계: km 플러그인 설정 + 선택적 로컬 도구 (5분, 권장)

현재 vault 검색은 km 플러그인의 `/km:search`가 담당합니다. 폴백 순서는
GraphRAG → Obsidian CLI → Obsidian MCP → text search입니다. 먼저 km 플러그인을
설정하세요.

```text
/km:setup
```

`/km:setup`은 저장 위치·MCP·vault 설정을 구성하지만 검색 도구를 설치하지는
않습니다. ThisCode의 `vault-search MCP`가 필요한 경우에만 아래 선택 단계를
진행하세요. 이 도구는 km의 Tier 3가 아닌 별도 로컬 도구입니다.

### 선택: ThisCode 로컬 vault-search MCP 설치 (5분)

```bash
bash ~/.claude/plugins/thiscode/scripts/install-vault-search.sh --apply
```

**✅ 성공 모습:** `vault-search added to claude config` 메시지

```bash
claude mcp list | grep vault-search
```

**✅ 성공 모습:** `vault-search` 항목 1줄 출력
**❌ 실패 시:**

- `claude: command not found` → Claude Code 미설치. https://claude.com/code 에서 설치
- npm install 실패 → `nvm use 18` 또는 `nvm install 18` 시도

**중요:** 선택 도구를 설치했다면 Claude Code 를 한 번 재시작하세요 (`exit` 후 재실행).

---

## 3단계: Obsidian 쓰시나요? 🤔

**예** → [3-A. Obsidian CLI 설치] 로 이동 (3분)
**아니오** → [3-B. Skip — Obsidian 없이도 잘 작동] 로 이동

### 3-A. Obsidian CLI 설치 (Obsidian 사용자만)

```bash
bash ~/.claude/plugins/thiscode/scripts/install-obsidian-cli.sh
```

**✅ 성공 모습:** 마지막 줄에 `obsidian-cli installed at /usr/local/bin/obsidian-cli` 비슷한 출력

```bash
which obsidian-cli
```

**✅ 성공 모습:** path 출력 (예: `/usr/local/bin/obsidian-cli`)
**❌ 실패 시:** brew/npm 설치 권한 → `sudo` 추가 시도, 또는 README 의 manual install 참고

### 3-B. Skip — Obsidian 없이도 잘 작동 ✅

- km `/km:search`는 GraphRAG → Obsidian CLI → Obsidian MCP → text search 순서로
  가능한 경로를 시도하고, 사용할 수 없는 경로는 건너뜁니다.
- km Tier 3를 대신하지 않습니다.
  ThisCode의 `vault-search MCP`는 별도 로컬 도구입니다.
- Obsidian graph view·백링크 UI와 Obsidian CLI 구조 질의는 사용할 수 없습니다.

**Obsidian 없이 뭐가 되고 뭐가 안 되나 (구체적으로):**

| 기능 | Obsidian 없이 | 설명 |
|---|---|---|
| Discord 봇 대화·작업 | ✅ 100% | Obsidian 과 무관 |
| 키워드 검색 (`ripgrep`) | ✅ 100% | 파일명·본문 문자 일치 검색 |
| 의미 기반 검색 (GraphRAG/MCP) | ✅ 가능 | 노트 폴더(.md 모음)만 있으면 됨 — Obsidian *앱* 필수 아님 |
| 노트 graph view·백링크 UI | ❌ | Obsidian 앱 전용 |
| Obsidian CLI 구조 질의 (tags·backlinks) | ❌ | Tier 2 만 빠짐 — 검색은 다른 Tier 가 대신 |

→ 결론: **첫 봇 운영엔 충분**합니다. 노트가 수백 개 이상 쌓이고 그래프
시각화가 필요해질 때 Obsidian 을 설치해도 늦지 않습니다. 바로 4단계로 진행

---

## 4단계: GraphRAG 까지 가실래요? 🚀

2가지 옵션 중 선택:

| 선택 | 누가? | 시간 |
|---|---|---|
| **A. 지금은 패스** | 빠르게 도입, text search부터 시작 | 0분 |
| **B. Python 로컬 설치** | 직접 디버깅 원하는 사용자 | 25분 |

### 4-A. 지금은 패스 ✅

→ 바로 5단계로

### 4-B. Python 로컬 설치

```bash
python3 --version   # 검증: 3.10+
bash ~/.claude/plugins/thiscode/scripts/install-graphrag.sh --apply
```

설치 시간 5-10분 + 첫 indexing 15분 = 총 ~25분.

**✅ 성공 모습:** `curl localhost:8400/health` → `{"status":"ok"}`

**❌ 실패 시:**

- Python 3.10 미설치 → macOS: `brew install python@3.11` / Ubuntu: `sudo apt install python3.11`
- pip install 실패 → `pip3 install --upgrade pip` 후 재시도

---

## 🎉 마지막 단계: 모든 게 잘 됐는지 확인

```bash
bash ~/.claude/plugins/thiscode/scripts/healthcheck.sh
```

**✅ 성공 모습 (예시 — 환경에 따라 각 단계의 상태가 달라집니다):**

```
thiscode healthcheck v2.3 — Phase progress
─────────────────────────────────
✓ Phase 0 superpowers (plugin)       : OK
✓ Phase 1 ripgrep (local text)        : OK
○ Phase 2 obsidian-cli (local tool)   : NOT YET
○ Phase 3 vault-search MCP (local embedding) : NOT YET
○ Phase 4 GraphRAG (local server)     : NOT YET
○ Phase 5 Dense embedding (4-channel): NOT YET
─────────────────────────────────
Summary: 2 OK, 4 NOT YET (all required passed) ✅
```

Exit code: `0` = all phases OK / `1` = required FAIL / `2` = optional phase가 아직 준비되지 않음.

**❌ 실패 시:**

```bash
cat ~/.thiscode-setup.log
```

이 파일 내용을 복사해서 GitHub Issue 등록:
👉 https://github.com/treylom/ThisCode/issues/new?template=setup-failure.yml

## 잘 됐나요? 첫 사용 해보기

Claude Code 안에서:

```
/thiscode:help
```

vault 검색을 써 보려면 km 플러그인을 먼저 설치합니다:

```
claude plugin marketplace add treylom/tofukyung-plugins
claude plugin install km@tofukyung-plugins
/km:search "안녕 첫 검색"
```

축하합니다! 🎉

---

## ❓ 자주 묻는 질문

**Q. 셋업 도중 중간에 멈춰도 되나요?**
A. 네. 각 단계가 독립적이라 text search(ripgrep)까지는 작동합니다.

**Q. macOS / Linux / Windows / WSL 다 됩니까?**
A. macOS / Linux / WSL 은 검증 완료. Windows native 는 추후 지원 예정 (현재 WSL 권장).

**Q. 학생인데 비용 걱정?**
A. km의 Tier 2 (Obsidian CLI)와 Tier 4 (text search)는 무료입니다. Tier 3
(Obsidian MCP)는 별도 로컬 MCP 서버로 구성하며 Claude Code 구독에 포함된다고
전제하지 않습니다. ThisCode의 선택적 `vault-search MCP`도 로컬에서 실행하는
별도 도구입니다. Tier 1 (GraphRAG)만 OpenAI/Anthropic API를 호출하므로 본인
vault 크기에 따라 1회 indexing 비용이 달라집니다.

**Q. 이미 obsidian-cli 만 쓰고 있는데 차이는?**
A. README 의 5-axis benchmark 표 참고. 예전 ThisCode 가이드 메모에는 당시 Obsidian CLI 기준선보다 GraphRAG recall이 높다고 적혀 있었지만, 보관된 2026-05-13 결과는 legacy engine ID(vault-search MCP는 2, Obsidian CLI는 3)로 Tier 1·2를 건너뛰어 정확한 상승률을 입증하지 않습니다. 이 메모는 역사적 기록이며 현재 km 플러그인 runtime 성능 비교를 뜻하지 않습니다. 현재는 Tier 2 Obsidian CLI(가벼운 로컬 검색)와 Tier 1 GraphRAG(semantic/graph 검색, 더 큰 셋업·API 비용)의 trade-off를 본인 fixture로 비교하고, 역사적 상승률은 재사용하지 마세요.

**Q. 피드백 어디 남기나요?**
A. GitHub Discussions Feedback category: https://github.com/treylom/ThisCode/discussions/categories/feedback (Round 3 outcome). 5 질문 schema 로 2분 응답 → v1.1 graduate decision 에 반영.

**Q. 도움이 필요해요!**
A. GitHub Issue: https://github.com/treylom/ThisCode/issues
   커뮤니티: GitHub Discussions
