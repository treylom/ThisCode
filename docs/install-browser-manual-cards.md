# 브라우저 설치 수동 복구 카드 A~E

자동 설치가 멈춘 단계와 같은 글자의 카드부터 시작합니다. 한 카드를 마치면 `/thiscode:install-browser`를 다시 실행하면 통과한 단계는 건너뜁니다.

## 카드 A — 0단계 환경 확인

### Windows PowerShell

```powershell
Get-Command node,npx,claude
```

세 명령의 위치가 모두 표시되면 카드 B로 갑니다. `claude`가 없으면 Claude Code 공식 설치를 먼저 마칩니다.

### macOS·Linux·WSL

```bash
command -v node npx claude
```

세 경로가 모두 표시되면 카드 B로 갑니다.

## 카드 B — 1단계 Node 준비

### Windows PowerShell

```powershell
winget install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
```

설치 후 PowerShell을 새로 열고 `/thiscode:install-browser`를 다시 실행합니다.

### macOS·Linux·WSL

```bash
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm install --lts
```

설치 후 터미널을 새로 열고 `/thiscode:install-browser`를 다시 실행합니다.

## 카드 C — 2단계 프로젝트 연결

프로젝트 폴더에서 한 번 실행합니다. `-s project`를 빼지 않습니다.

### Windows PowerShell·macOS·Linux·WSL 공통

```text
claude mcp add -s project playwright -- npx @playwright/mcp@latest
```

성공 화면에 `project config`와 `playwright`가 보이면 `/thiscode:install-browser`를 다시 실행합니다.

## 카드 D — 3단계 Chromium 준비

먼저 저장 공간을 15 GiB 이상 확보합니다. 그다음 한 번 실행합니다.

### Windows PowerShell·macOS·Linux·WSL 공통

```text
npx playwright install chromium
```

다운로드가 끝나면 `/thiscode:install-browser`를 다시 실행합니다.

## 카드 E — 4단계 실행 확인

프로젝트 폴더에서 새 Claude Code 세션을 엽니다.

```text
claude
```

프로젝트의 Playwright 연결을 승인한 뒤 `/thiscode:install-browser`를 다시 실행합니다. 화면에 다음 두 문장이 모두 보여야 자동 설치와 일반 세션이 같은 승인 상태를 검증한 것입니다.

> 4b 승인 상태 확인: 프로젝트 Playwright 연결 승인됨
>
> 브라우저 준비가 끝났습니다. 프로젝트 Playwright 연결 승인 상태까지 확인했습니다. 이 프로젝트에서 웹페이지 열기와 화면 읽기를 사용할 수 있습니다.

그다음 다음 문장을 입력합니다.

```text
Playwright로 https://example.com 을 열고 페이지 제목과 화면 구조를 확인해줘.
```

제목 `Example Domain`과 페이지 스냅샷이 함께 보이면 실행 확인이 끝난 것입니다. 둘 중 하나만 보이면 카드 E를 반복하지 말고 화면의 첫 오류 문구를 보조강사에게 전달합니다.
