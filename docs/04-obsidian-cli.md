# 04. Obsidian CLI 설정

> Obsidian vault 를 명령행에서 직접 조작하기 위한 CLI. Claude Code 의 vault 접근 3-Tier 폴백 (CLI → MCP → Write/Read/Grep) 의 1순위.

## 왜 Obsidian CLI 인가

vault 안 노트 조작 시 3 가지 방법 비교:

| Tier | 방법 | 장점 | 단점 |
|---|---|---|---|
| 1 | **Obsidian CLI** | wikilink 자동 업데이트, 메타데이터 정확, native search | 환경별 install 다름, 일부 명령 버그 (예: `search:context` exit 255, `deadends` JSON 미지원) |
| 2 | **Obsidian MCP server** | Claude Code agent 가 도구 형태로 호출, programmatic | MCP server 설치 + 인증 필요 |
| 3 | **Write/Read/Grep** | 의존성 0, 어디서나 작동 | wikilink 안 업데이트, 메타데이터 손상 가능 |

→ **1 → 2 → 3 폴백** 패턴. thiscode 의 skills/agents 가 본 순서대로 시도.

## 환경별 install

### Mac (Homebrew)

```bash
# Obsidian app 자체 (data 저장소 + GUI)
brew install --cask obsidian

# Obsidian CLI binary 확인
ls /opt/homebrew/bin/obsidian 2>/dev/null
obsidian --version
```

→ `/opt/homebrew/bin/obsidian` 위치. brew formula 가 자동 link.

### Linux (Debian/Ubuntu)

```bash
# Option A — AppImage 또는 deb 다운로드
# https://obsidian.md/download
wget https://github.com/obsidianmd/obsidian-releases/releases/latest/download/obsidian_*_amd64.deb
sudo dpkg -i obsidian_*_amd64.deb

# Option B — Snap
sudo snap install obsidian --classic

# Option C — Flatpak
flatpak install flathub md.obsidian.Obsidian
```

### WSL (Windows Subsystem for Linux)

WSL 자체에는 Obsidian app 안 설치. **Windows native binary 호출**:

```bash
# Windows native Obsidian path
WIN_OBSIDIAN="/mnt/c/Program Files/Obsidian/Obsidian.com"

# WSL alias 등록 (선택)
alias obsidian="'$WIN_OBSIDIAN'"
```

→ WSL 안에서 `obsidian` 호출 시 Windows 의 Obsidian 시동.

⚠️ **WSL 의 알려진 한계**: WSL `/mnt/c/...` 경로 30-40% I/O 성능 저하 (Windows native filesystem layer). vault 가 큰 경우 (>10K notes) 그래프 뷰 로딩 65-90% 단축 가능 (Defender 제외 + 플러그인 정리). 자세히는 vault `020-Library/Research/2026-04-29-obsidian-cli-graph-view-loading/Q5-Windows-그래프-로딩-단축.md` 참조.

## vault 경로 설정

### Mac (default)

```bash
VAULT="$HOME/Documents/<vault-name>"
# 예: $HOME/Documents/Second_Brain
```

### WSL (Windows vault sharing)

```bash
VAULT="/mnt/c/Users/<windows-user>/Documents/Obsidian/<vault-name>"
# 예: <vault>
```

⚠️ **경로 정규화 주의**: Claude Code 슬래시 (`/km:search` 등) 가 vault root 기준 **상대 경로** 만 받음. 다음 패턴 금지:

```
❌ Second_Brain/Library/Zettelkasten/note.md   # 중첩!
✅ Library/Zettelkasten/note.md                 # vault root 기준
```

## 3-Tier 폴백 패턴 — Claude Code 안에서

thiscode 의 skills 가 vault 접근 시 자동 시도:

```python
# Pseudocode (실제 skill 안 진행)
try:
    # Tier 1: Obsidian CLI
    result = subprocess.run(["obsidian", "search", "query"], ...)
except (FileNotFoundError, subprocess.CalledProcessError):
    try:
        # Tier 2: Obsidian MCP
        result = mcp__obsidian__search(query)
    except MCPError:
        # Tier 3: Write/Read/Grep
        result = grep_vault(query)
```

→ 사용자 환경에 따라 Tier 1 또는 2 또는 3 작동. wizard 가 환경 인식 후 default 시도 순서 설정.

## 알려진 버그 + 워크어라운드

### `obsidian search:context` exit 255

context 안 명령. 다음 명령으로 우회:
```bash
obsidian search "키워드"   # 단순 매칭
# 또는
grep -rn "키워드" <vault>/
```

### `obsidian deadends` JSON format 미지원

```bash
# ❌ 작동 안 함
obsidian deadends --format=json

# ✅ 우회
obsidian deadends 2>&1 | python3 -c "import sys, json; ..."
```

### Mac `/search` GraphRAG 인덱스 미배포 (deep 모드 약점)

Mac 환경에서 `/search --deep` 호출 시 GraphRAG FastAPI (port 8400) 와 로컬 SQLite 인덱스 둘 다 미배포 → 4차 폴백 Obsidian CLI + Grep 만 가능 → semantic 연결 탐지 실패.

회복: vault 안 GraphRAG 빌드 또는 vault-search MCP 활용. 자세히는 vault `<vault>/.claude-memory/machine-mac/project_search_fallback_mac_weak.md` 참조.

## Obsidian URI scheme (CLI 외 활용)

명령행에서 Obsidian app 의 특정 노트 열기:

```bash
# 형식
obsidian "obsidian://open?vault=<vault-name>&file=<path-to-note>"

# 예
obsidian "obsidian://open?vault=Second_Brain&file=Library%2FZettelkasten%2Fnote.md"
```

또는 search:
```bash
obsidian "obsidian://search?vault=Second_Brain&query=AI%20agent"
```

URL encoding 주의 (space → `%20`, `/` → `%2F`).

## 자가 검증 5-step

`/thiscode:start` wizard 의 일부 (또는 manual):

```bash
# Step 1. binary 존재
command -v obsidian || echo "Obsidian CLI 미설치"

# Step 2. vault 경로 존재
[ -d "$VAULT" ] && echo "vault 존재: $VAULT" || echo "VAULT 경로 invalid"

# Step 3. search 동작 (단순 매칭)
obsidian search "test" 2>&1 | head -5

# Step 4. open URI scheme
obsidian "obsidian://open?vault=<vault-name>" &
sleep 1; kill $! 2>/dev/null

# Step 5. MCP fallback 확인 (Tier 2)
claude mcp list 2>&1 | grep -i obsidian
```

## 관련 자원

- vault `<vault>/.claude/skills/vault-navigation.md` — vault 구조 + 태그 체계
- vault `<vault>/.claude/skills/km-archive-reorganization.md` — Obsidian CLI 3-Tier 폴백 패턴 예시
- vault `<vault>/.claude-memory/machine-mac/project_search_fallback_mac_weak.md` — Mac GraphRAG 약점
- thiscode skill: [../skills/bootstrap/SKILL.md](../skills/bootstrap/SKILL.md)
- 메인 wizard: [../commands/start.md](../commands/start.md)
