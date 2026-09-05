---
title: Dogfood Sandbox — WSL Ubuntu mimic
order: 9
---

# Dogfood Sandbox

WSL Ubuntu 20.04 환경에 가까운 Docker 컨테이너에서 km 플러그인의 4-Tier search와
KM 흐름을 자동 검증합니다. ThisCode 설치 스크립트가 준비하는 로컬 도구 검사는
별도 축이며 km의 fallback 구현을 대신하지 않습니다.

## 빌드 + 실행

```bash
# 1. sandbox 컨테이너 build (한 번만)
docker build -t thiscode-sandbox -f sandbox/Dockerfile .

# 2. (선택) docker-compose 사용
docker compose -f sandbox/docker-compose.yaml up -d
docker compose -f sandbox/docker-compose.yaml exec sandbox bash

# 3. 컨테이너 안에서 전체 dogfood 실행
bash /thiscode/tests/dogfood/run-all.sh
```

## 시나리오

| ID | 이름 | 검증 |
|---|---|---|
| Dog-1 | grep only (Obsidian 부재) | Tier 4 notice 출력 |
| Dog-2 | vault-search MCP install | Claude config jq merge OK |
| Dog-3 | GraphRAG check | server down 시에도 rc ≤ 4 |

## 결과 위치

`tests/dogfood/dogfood-results-<date>.md` 에 PASS/FAIL summary + host 정보 기록.

## 한계

- **MCP 호출 불가**: vault-search MCP 는 Claude Code / Hermes runtime 안에서만 호출됨. sandbox 의 Dog-2 는 config 설치까지만 검증.
- **GraphRAG 서버 띄움 X**: sandbox 가 vault 본인 인덱스 없으므로 `--apply` 실행 X. 실제 dogfood 는 host 머신에서 `bash scripts/install-graphrag.sh --apply` 후 진행.
- **sample-vault 의존**: Dog-1 은 `sample-vault/` 가 채워져 있어야 의미 있는 hit. Phase A (Codex 별도 spawn) 가 완료된 후 실행.

## 후속

- 실제 WSL 머신 (지인) 에서 install.sh 1-line dogfood (어제 §0.5)
- macOS native dogfood (별도 host)
- CI/CD: GitHub Actions 에서 `sandbox/Dockerfile` build + `run-all.sh` 자동 (잔존 task)
