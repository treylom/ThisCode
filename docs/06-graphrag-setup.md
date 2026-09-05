---
title: GraphRAG 수동 설치 가이드
order: 6
---

# GraphRAG 서버 (Tier 1) 수동 설치

자동 설치 (`install-graphrag.sh --apply`)가 실패하면 본 가이드 따라 수동 진행.

## 요구 환경

- Python 3.11+ (venv 지원)
- 4GB+ RAM
- vault root (Obsidian 사용 가정; 인덱스 대상 경로는 vendored CLI의 `--vault` 옵션으로 지정)

## 단계

1. vault 안 `.team-os/graphrag/` 폴더 신설 (또는 git clone 으로 가져옴)
2. `python3 -m venv .venv`
3. `.venv/bin/pip install -r requirements.txt`
4. `bash scripts/install-graphrag.sh --apply` — vendor(`vendor/graphrag/scripts/`)에서 인덱스 빌드 + `search_server` 기동(자동)

## 검증

```bash
curl http://127.0.0.1:8400/health
# 응답: {"status":"ok","index_version":"..."}
```

## 자원 자동 점검 (RAM)

`install-graphrag.sh` preflight 가 RAM 을 자동 점검합니다. **8GB 미만이면 GraphRAG(Tier 1) 비권장** — 메모리 과다로 thrash 위험. 이 경우 자동으로 **Obsidian CLI(Tier 2) 사용을 권고**하고, `--apply` 는 중단됩니다(`GRAPHRAG_FORCE=1` 로 강행 가능). 저사양 머신은 `bash scripts/install-obsidian-cli.sh` 로 Tier 2 를 쓰세요.

## 문제 해결

- 8400 포트 충돌: installer는 8400을 고정 사용하므로 해당 포트를 점유한 프로세스를 확인·정리한 뒤 재시도하고, 별도 서버를 직접 구성했다면 km 설정의 endpoint를 그 URL로 지정
- Index build 실패: vendored CLI에 `--vault <path>`를 명시하고 frontmatter를 검증 (`type:` 누락 노트 점검)
