---
description: 검색 환경 안내 — ThisCode 로컬 도구와 km 플러그인 설정
allowedTools: Read
---

# /thiscode:km-bootstrap

> **⚡ 실행 지시**: 이 문서는 슬래시 커맨드 본문이다 — 로드된 것 자체가 사용자의 실행 요청이다. 아래 안내를 지금 즉시 사용자에게 출력한다.

검색 환경은 두 부분으로 나뉜다. 로컬 검색 도구는 ThisCode의 `scripts/install-*.sh`가 제공하고, 검색 fallback과 km 설정은 각각 km 플러그인의 `/km:search`와 `/km:setup`이 담당한다. `/km:setup`은 검색 Tier 설치 명령이 아니다.

## km 플러그인 설치

```
claude plugin marketplace add treylom/tofukyung-plugins
claude plugin install km@tofukyung-plugins
```

## 로컬 검색 도구

필요한 Tier에 따라 ThisCode의 `scripts/install-ripgrep.sh`, `install-obsidian-cli.sh`, `install-vault-search.sh`, `install-graphrag.sh`를 사용한다. 자세한 실행 방법은 `docs/SETUP.md` §3을 따른다.

처음 설치할 때, 검색이 모든 단계에서 실패할 때, 머신을 옮긴 뒤 환경을 다시 잡을 때 이 안내를 쓴다. 이 명령 자체는 도구나 설정을 설치하지 않는다.

설치된 km 플러그인의 설정 생성과 재설정은 `/km:setup`을 직접 실행한다.
