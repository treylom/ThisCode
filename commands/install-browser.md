---
description: Playwright 브라우저 도구를 단계별로 자동 설치하고 새 세션에서 실행까지 확인
allowed-tools: Bash Read
disable-model-invocation: true
---

# /thiscode:install-browser — 브라우저 자동 설치

> **실행 지시**: 이 명령이 로드되면 설명이나 추가 확인 질문으로 멈추지 않습니다. 아래 0→4단계를 순서대로 즉시 실행합니다. 한 단계가 실패하면 다음 단계로 가지 않고, 출력된 수동 카드부터 안내합니다.

## 진행 규칙

- 각 단계에서는 아래 명령 **한 개만** 실행합니다.
- exit 0일 때만 다음 단계로 갑니다.
- 실패 화면은 정확히 `n단계 실패 → 수동 카드 X` 형식으로 보여줍니다.
- 사용자에게 내부 판정 파일이나 구현 언어를 설명하지 않습니다. 화면에는 지금 하는 일과 결과만 보여줍니다.
- 문장은 권유형이 아니라 실행형으로 씁니다: `지금 환경을 확인합니다`, `지금 브라우저 도구를 연결합니다`.

## 0단계 — 환경 확인

화면: `지금 이 컴퓨터의 환경을 확인합니다.`

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-browser-gate.sh" 0
```

실패하면 중단하고 `docs/install-browser-manual-cards.md`의 카드 A를 안내합니다.

## 1단계 — Node 준비

화면: `지금 실행 기반을 준비합니다. 이미 준비되어 있으면 건너뜁니다.`

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-browser-gate.sh" 1
```

실패하면 중단하고 카드 B를 안내합니다.

## 2단계 — 프로젝트에 브라우저 도구 연결

화면: `지금 이 프로젝트에만 브라우저 도구를 연결합니다.`

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-browser-gate.sh" 2
```

실패하면 중단하고 카드 C를 안내합니다. 사용자 전체 설정으로 바꾸지 않습니다.

## 3단계 — Chromium 준비

화면: `지금 웹페이지를 열 Chromium을 준비합니다. 이미 있으면 건너뜁니다.`

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-browser-gate.sh" 3
```

실패하면 중단하고 카드 D를 안내합니다. 여유 공간이 15 GiB 미만이면 다운로드하지 않고 중단합니다.

## 4단계 — 새 세션 실행 확인

화면: `지금 새 세션에서 예제 페이지를 열고 제목과 화면 구조를 확인합니다.`

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-browser-gate.sh" 4
```

exit 0이면 다음 완료 화면만 보여줍니다.

> 브라우저 준비가 끝났습니다. 이 프로젝트에서 웹페이지 열기와 화면 읽기를 사용할 수 있습니다.

실패하면 카드 E를 안내합니다. 모델의 “성공했습니다” 문장이 아니라 페이지 열기·스냅샷·제목의 기계 이벤트 3개로 판정합니다.
