# Architecture — thiscode v1.0

thiscode 의 구조 + 흐름을 mermaid 차트로 시각화. GitHub 에서 자동 render — 별도 도구 불필요.

## 1. km plugin search fallback (external)

아래 검색 fallback은 km 플러그인이 소유하고 실행합니다. 현재 순서는
GraphRAG → Obsidian CLI → Obsidian MCP → text search입니다. ThisCode는 봇
하네스와 별도의 로컬 도구 설치기를 제공하며, 그 설치기가 제공하는
`vault-search MCP`는 이 km 검색 흐름에 포함되지 않습니다.

> 이 차트는 현재 km fallback의 순서만 보여 줍니다. latency/recall 수치는
> 현재 km runtime의 성능값으로 싣지 않으며, 역사적 로컬 도구 범위는
> [BENCHMARK.md](BENCHMARK.md)에 당시 도구 ID와 함께 남아 있습니다.

```mermaid
flowchart TD
    Start([사용자 query]) --> Disp{dispatcher}

    Disp -->|시작| T1[Tier 1<br/>GraphRAG]
    T1 -->|결과 있음| Return([결과 반환])
    T1 -->|미설치/server down| T2

    T2[Tier 2<br/>Obsidian CLI] -->|결과 있음| Return
    T2 -->|미설치| T3

    T3[Tier 3<br/>Obsidian MCP] -->|결과 있음| Return
    T3 -->|미설치| T4

    T4[Tier 4<br/>text search] --> Return

    classDef tier1 fill:#fff8e1,stroke:#f57c00,stroke-width:2px
    classDef tier2 fill:#f0f4ff,stroke:#1976d2,stroke-width:2px
    classDef tier3 fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    classDef tier4 fill:#f5f5f5,stroke:#616161,stroke-width:2px
    class T1 tier1
    class T2 tier2
    class T3 tier3
    class T4 tier4
```

ThisCode의 별도 로컬 도구는 `scripts/install-*.sh`로 설치합니다. `/km:search`는
위의 km fallback을 실행하고 `/km:setup`은 km 저장 위치·MCP·설정을 구성하며,
검색 Tier 설치를 대신하지 않습니다.

---

## 2. km plugin commands — 외부 플러그인

```mermaid
flowchart LR
    User([사용자]) -->|`/km:search`| Search[검색 fallback]
    User -->|`/km:knowledge-manager`| Knowledge[지식관리 workflow]
    User -->|`/km:setup`| Setup[플러그인 설정 생성]

    Search --> Out1([검색 결과])
    Knowledge --> Out2([수집·분류·저장])
    Setup --> Out3([설정 완료])

    classDef command fill:#e3f2fd,stroke:#1976d2
    class Search,Knowledge,Setup command
```

---

## 3. 회의실 4-file Lifecycle

다 봇 협업 회의 시 회의록 폴더 + 4-file template 자동 셋업.

```mermaid
flowchart TB
    Cmd[/`/thiscode:meetings new spec-review`/] --> Mkdir[.claude-meetings/2026-05-13-spec-review/ 생성]

    Mkdir --> F1[00-agenda.md<br/>의제 + 참가자 + 시간]
    Mkdir --> F2[01-spec.md<br/>baseline 결정]
    Mkdir --> F3[02-progress.md<br/>진행 상황]
    Mkdir --> F4[03-outcome.md<br/>합의 결론 + 후속]

    F1 --> R1[Round 1<br/>GPT-5.5 baseline]
    R1 --> R2[Round 2<br/>심도 deep dive]
    R2 --> R3[Round 3<br/>cross-check]
    R3 --> F4

    F4 --> Spec[spec/plan 보강]
    Spec --> Exec[실행 진입]

    classDef file fill:#e8f5e9,stroke:#388e3c
    class F1,F2,F3,F4 file
```

본 매뉴얼 자체가 outcome 예시: `.claude-meetings/2026-05-13-thiscode-yaml-v1.0/` → 3 라운드 GPT-5.5 토론 → 12 decisions → v1.0 spec 확정 → 19 task 실행 → release.

---

## 4. Custom Hybrid YAML — 5 Block 구조

`.agents/<name>.yaml` 한 파일이 5 block 으로 구성됨.

```mermaid
flowchart TD
    YAML([.agents/your-agent.yaml]) --> BA[Block A<br/>agentskills.io base<br/>name + description + version + license]
    YAML --> BB[Block B<br/>Hermes provides_*<br/>tools + hooks + commands]
    YAML --> BC[Block C<br/>thiscode extension<br/>tier + model + allowedTools]
    YAML --> BD[Block D<br/>Dynamic gates<br/>expr + evaluator simple/cel]
    YAML --> BE[Block E<br/>Benchmark integration<br/>fixtures + axes + baseline_tier]

    BA --> CT[Cross-tool compat<br/>Claude/Cursor/Aider]
    BB --> LR[Lifecycle registration]
    BC --> CP[Classroom policy<br/>external/internal/experimental/deprecated]
    BD --> GV[Gate verification<br/>PR 머지 전 강제 검증]
    BE --> RM[README 표 5-axis<br/>auto-update]

    classDef block fill:#f0f4ff,stroke:#1976d2
    class BA,BB,BC,BD,BE block
```

각 Block 책임 분리 — Block A 만 cross-tool portable, Block C/D/E 는 thiscode 전용 extension.

---

## 5. v1.0 → v1.1 Graduate Timeline

```mermaid
gantt
    title v1.0 → v1.1 graduate 사이클 (2026-05-13 ~ 2026-06-04)
    dateFormat YYYY-MM-DD
    axisFormat %m/%d

    section v1.0 Release
    YAML 표준화 + Plan 19 task    :done, plan, 2026-05-13, 1d
    18 commits push + tag v1.0.0  :done, push, 2026-05-13, 1d

    section 2-week Lock
    1차 코호트 dogfood            :active, dogfood, 2026-05-13, 14d
    GitHub Discussions feedback   :feedback, 2026-05-13, 14d
    Mac Mini Tier 1 weekly cron   :cron, 2026-05-13, 14d

    section v1.1 Decision
    Drift + feedback 분석         :analysis, 2026-05-27, 1d
    v1.1 graduate decision        :crit, decide, 2026-05-28, 1d
    agents-migrate.mjs 작성       :migrate, 2026-05-28, 2d
    v1.1 PR 머지 + vault mirror   :crit, release, 2026-06-04, 1d
```

Graduate trigger 3 조건 (Round 3 outcome):
1. benchmark/results 3주 연속 metric ±20% 이상 drift
2. GitHub Discussions feedback "재현 성공률 ⚠️/❌" 3건 이상
3. `tier1-stale > 14 days` badge 14일 지속

---

## 6. 전체 통합 (요약)

```mermaid
flowchart LR
    subgraph User[사용자 환경]
        CC[Claude Code]
        Vault[(vault)]
    end

    subgraph Plugin[thiscode plugin]
        Meet[/thiscode:meetings<br/>회의실/]
        Setup[/thiscode:setup<br/>bootstrap/]
    end

    subgraph KMPlugin[km plugin — external]
        Search[/km:search<br/>vault fallback/]
        Knowledge[/km:knowledge-manager<br/>지식관리/]
        KMSetup[/km:setup<br/>configuration/]
    end

    subgraph Backend[검색 backend]
        T1[Tier 1<br/>GraphRAG]
        T2[Tier 2<br/>Obsidian CLI]
        T3[Tier 3<br/>Obsidian MCP]
        T4[Tier 4<br/>text search]
    end

    subgraph CI[GitHub Actions]
        VA[validate-agents.yml<br/>PR check]
        BM[benchmark.yml<br/>main push 자동]
        BT1[benchmark-tier1.yml<br/>biweekly Docker]
    end

    CC --> Search
    CC --> Knowledge
    CC --> KMSetup
    CC --> Meet
    CC --> Setup

    Search --> T1
    Search --> T2
    Search --> T3
    Search --> T4

    T1 --> Vault
    T2 --> Vault
    T3 --> Vault
    T4 --> Vault

    Plugin -.PR.-> VA
    Plugin -.main push.-> BM
    BM -.biweekly.-> BT1
    BM -.auto-PR.-> README[README.md<br/>benchmark 표]

    classDef user fill:#e3f2fd,stroke:#1976d2
    classDef plugin fill:#fff8e1,stroke:#f57c00
    classDef external fill:#ede7f6,stroke:#6a1b9a
    classDef backend fill:#e8f5e9,stroke:#388e3c
    classDef ci fill:#fce4ec,stroke:#c2185b
    class CC,Vault user
    class Meet,Setup plugin
    class Search,Knowledge,KMSetup external
    class T1,T2,T3,T4 backend
    class VA,BM,BT1,README ci
```

---

## 관련 문서

- [README.md](../README.md) — 5-axis benchmark 표 + 빠른 시작
- [SETUP.md](SETUP.md) — 개발자용 5단계 셋업
- [SETUP-BEGINNER.md](SETUP-BEGINNER.md) — 초보자용 분기 친절 + FAQ
- [SETUP-BEGINNER.typ / .pdf](SETUP-BEGINNER.typ) — 인쇄용 typst PDF
- [MANUAL.typ / .pdf](MANUAL.typ) — 13 sections 완전 매뉴얼
- [AGENTS.md](AGENTS.md) — Custom Hybrid v1.0 spec
- [BENCHMARK.md](BENCHMARK.md) — 5-axis 측정 방법 + 해석
