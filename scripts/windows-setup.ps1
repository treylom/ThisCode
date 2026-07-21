# ThisCode Windows setup kit — one command, no admin required.
#   irm https://raw.githubusercontent.com/treylom/ThisCode/main/scripts/windows-setup.ps1 | iex
#
# What it does (every step is NON-FATAL — on failure it prints the manual command and moves on):
#   1. PowerShell ExecutionPolicy (CurrentUser RemoteSigned) so $PROFILE loads
#   2. Bun runtime (required by the official Discord plugin's MCP server)
#   3. Real Python (detects the WindowsApps store stub that pretends to run)
#   4. PATH for this session + profile (~/.bun/bin, ~/.local/bin where claude.exe lives)
#   5. Creates $PROFILE if missing
#   6. Final diagnosis table: what is ready, what still needs a manual step
#
# Designed for managed/GPO lab machines: nothing here requires admin, and any
# blocked step degrades to a printed manual alternative instead of aborting.

$ErrorActionPreference = 'Continue'
$report = [ordered]@{}

function Step($name, [scriptblock]$body, $manualHint) {
  Write-Host "`n== $name" -ForegroundColor Cyan
  try {
    & $body
    $script:report[$name] = 'OK'
  } catch {
    Write-Host "   실패(계속 진행): $($_.Exception.Message)" -ForegroundColor Yellow
    if ($manualHint) { Write-Host "   수동 명령: $manualHint" -ForegroundColor Yellow }
    $script:report[$name] = "수동 필요: $manualHint"
  }
}

Step 'ExecutionPolicy (프로필 로드 전제)' {
  $cur = Get-ExecutionPolicy -Scope CurrentUser
  if ($cur -in @('Restricted','Undefined','AllSigned')) {
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
    Write-Host "   CurrentUser → RemoteSigned"
  } else { Write-Host "   이미 $cur — 변경 없음" }
  # GPO(MachinePolicy)가 우선하면 CurrentUser 변경이 무력할 수 있음 — 진단만 남긴다
  $gpo = Get-ExecutionPolicy -Scope MachinePolicy
  if ($gpo -notin @('Undefined')) {
    Write-Host "   ⚠ 조직 정책(MachinePolicy=$gpo)이 우선입니다 — 프로필이 계속 안 읽히면:" -ForegroundColor Yellow
    Write-Host "     powershell -ExecutionPolicy Bypass 로 창을 열어 사용하세요" -ForegroundColor Yellow
  }
} 'Set-ExecutionPolicy -Scope CurrentUser RemoteSigned'

Step 'Bun 런타임 (Discord 플러그인 필수)' {
  if (Get-Command bun -ErrorAction SilentlyContinue) {
    Write-Host "   이미 설치됨: $(bun -v)"
  } else {
    irm bun.sh/install.ps1 | iex
    if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
      $env:Path = "$HOME\.bun\bin;$env:Path"
    }
    Write-Host "   설치 완료: $(bun -v)"
  }
} 'irm bun.sh/install.ps1 | iex'

Step 'Python 실설치 (스토어 스텁 감지)' {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if ($py -and $py.Source -notlike '*WindowsApps*') {
    Write-Host "   이미 실설치: $($py.Source)"
  } else {
    if ($py) { Write-Host "   WindowsApps 스텁 감지 ($($py.Source)) — 실설치 진행" }
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    Write-Host "   winget 설치 요청 완료 — 새 터미널에서 python --version 으로 확인"
  }
} 'winget install -e --id Python.Python.3.12  (winget 불가 시 https://python.org 설치 파일)'

Step 'PATH (bun · claude)' {
  foreach ($p in @("$HOME\.bun\bin", "$HOME\.local\bin")) {
    if ((Test-Path $p) -and ($env:Path -notlike "*$p*")) { $env:Path = "$p;$env:Path" }
  }
  $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
  foreach ($p in @("$HOME\.bun\bin", "$HOME\.local\bin")) {
    if ((Test-Path $p) -and ($userPath -notlike "*$p*")) {
      [Environment]::SetEnvironmentVariable('Path', "$p;$userPath", 'User')
      $userPath = "$p;$userPath"
      Write-Host "   User PATH에 추가: $p"
    }
  }
} '[Environment]::SetEnvironmentVariable("Path", "$HOME\.bun\bin;" + [Environment]::GetEnvironmentVariable("Path","User"), "User")'

Step '$PROFILE 생성' {
  if (!(Test-Path $PROFILE)) {
    New-Item -ItemType File -Force $PROFILE | Out-Null
    Write-Host "   생성: $PROFILE"
  } else { Write-Host "   이미 있음: $PROFILE" }
} 'New-Item -ItemType File -Force $PROFILE'

# ---- 최종 진단 -------------------------------------------------------------
Write-Host "`n===== 진단 요약 =====" -ForegroundColor Green
foreach ($k in $report.Keys) { Write-Host ("  {0}: {1}" -f $k, $report[$k]) }

$diag = [ordered]@{
  'bun'    = if (Get-Command bun -ErrorAction SilentlyContinue) { "✅ $(bun -v)" } else { '❌ 새 터미널에서 재확인' }
  'python' = & {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py -and $py.Source -notlike '*WindowsApps*') { "✅ $($py.Source)" }
    elseif ($py) { '⚠ 스토어 스텁 — 새 터미널에서 재확인' } else { '❌ 미설치' } }
  'claude' = & {
    $c = Get-Command claude -ErrorAction SilentlyContinue
    if ($c) { "✅ $($c.Source)" }
    elseif (Test-Path "$HOME\.local\bin\claude.exe") { "✅ $HOME\.local\bin\claude.exe (PATH 반영은 새 터미널부터)" }
    else { '❌ 미설치 — irm https://claude.ai/install.ps1 | iex' } }
}
Write-Host "`n===== 도구 상태 =====" -ForegroundColor Green
foreach ($k in $diag.Keys) { Write-Host ("  {0}: {1}" -f $k, $diag[$k]) }

Write-Host @"

다음 단계:
  1) 새 터미널을 열고 (PATH·정책 반영)
  2) claude 실행 → /plugin 에서 discord@claude-plugins-official 설치
  3) /thiscode:create-bot 으로 봇 생성
  4) 봇 실행은 반드시 --channels 포함:
     claude --channels plugin:discord@claude-plugins-official
"@ -ForegroundColor Green
