# ThisCode Windows setup kit — one command, no admin required.
#   irm https://raw.githubusercontent.com/treylom/ThisCode/main/scripts/windows-setup.ps1 | iex
#   (or double-click scripts/windows-setup.bat)
#
# What it does (every step is NON-FATAL — on failure it prints the manual command and moves on):
#   1. PowerShell ExecutionPolicy (CurrentUser RemoteSigned) so $PROFILE loads
#   2. Bun runtime (required by the official Discord plugin's MCP server)
#   3. Real Python (detects the WindowsApps store stub that pretends to run)
#   4. PATH for this session + profile (~/.bun/bin, ~/.local/bin where claude.exe lives)
#   5. Creates $PROFILE if missing
#   6. Final diagnosis table: OK / PENDING_RESTART / MANUAL_REQUIRED per step
#
# Designed for managed/GPO lab machines: nothing here requires admin, and any
# blocked step degrades to a printed manual alternative instead of aborting.
# Error contract: inside each Step, errors are promoted to terminating
# ($ErrorActionPreference='Stop'), native commands are checked via
# $LASTEXITCODE, body stdout goes to the host (never captured as status),
# and non-OK outcomes travel only through $script:StepStatus —
# so a failed step can never be recorded as OK.

$ErrorActionPreference = 'Continue'
$report = [ordered]@{}

function Step($name, [scriptblock]$body, $manualHint) {
  Write-Host "`n== $name" -ForegroundColor Cyan
  $prevEap = $ErrorActionPreference
  $script:StepStatus = $null          # 상태는 이 변수로만 전달 (stdout 혼입 차단 —
  try {                               #  scriptblock 반환값은 native stdout 전체를 배열로 포획하므로 쓰지 않는다)
    $ErrorActionPreference = 'Stop'   # cmdlet non-terminating errors → catch
    & $body | Out-Host                # native/cmdlet stdout은 화면으로만
    $status = if ($script:StepStatus) { $script:StepStatus } else { 'OK' }
    $script:report[$name] = $status
  } catch {
    Write-Host "   실패(계속 진행): $($_.Exception.Message)" -ForegroundColor Yellow
    if ($manualHint) { Write-Host "   수동 명령: $manualHint" -ForegroundColor Yellow }
    $script:report[$name] = "MANUAL_REQUIRED: $manualHint"
  } finally {
    $ErrorActionPreference = $prevEap
  }
}

Step 'ExecutionPolicy (프로필 로드 전제)' {
  $cur = Get-ExecutionPolicy -Scope CurrentUser
  if ($cur -in @('Restricted','Undefined','AllSigned')) {
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
    if ((Get-ExecutionPolicy -Scope CurrentUser) -ne 'RemoteSigned') { throw "CurrentUser 정책이 변경되지 않음 (조직 정책 의심)" }
    Write-Host "   CurrentUser → RemoteSigned"
  } else { Write-Host "   이미 $cur — 변경 없음" }
  # GPO(MachinePolicy)가 우선하면 CurrentUser 변경이 무력 — false OK 금지, 수동 상태로 기록
  $gpo = Get-ExecutionPolicy -Scope MachinePolicy
  if ($gpo -in @('Restricted','AllSigned')) {
    Write-Host "   ⚠ 조직 정책(MachinePolicy=$gpo)이 우선입니다 — 프로필 로드가 계속 막히면:" -ForegroundColor Yellow
    Write-Host "     powershell -ExecutionPolicy Bypass 로 창을 열어 사용하세요" -ForegroundColor Yellow
    $script:StepStatus = 'MANUAL_REQUIRED: 조직 정책 우선 — powershell -ExecutionPolicy Bypass 창 사용'
  }
} 'Set-ExecutionPolicy -Scope CurrentUser RemoteSigned'

Step 'Bun 런타임 (Discord 플러그인 필수)' {
  $existing = Get-Command bun -ErrorAction SilentlyContinue
  if ($existing) {
    $v = & $existing -v
    if ($LASTEXITCODE -ne 0) { throw "bun 이 있으나 실행 실패 (exit $LASTEXITCODE)" }
    Write-Host "   이미 설치됨: $v"
    return
  }
  irm bun.sh/install.ps1 | iex
  $env:Path = "$HOME\.bun\bin;$env:Path"
  $bunExe = Get-Command bun -ErrorAction SilentlyContinue
  if (-not $bunExe) { throw "설치 스크립트는 끝났지만 bun 실행 파일을 찾지 못함" }
  $v = & $bunExe -v
  if ($LASTEXITCODE -ne 0) { throw "bun 실행 실패 (exit $LASTEXITCODE)" }
  Write-Host "   설치 완료: $v"
} 'irm bun.sh/install.ps1 | iex'

Step 'Python 실설치 (스토어 스텁 감지)' {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if ($py -and $py.Source -notlike '*WindowsApps*') {
    Write-Host "   이미 실설치: $($py.Source)"
    return
  }
  if ($py) { Write-Host "   WindowsApps 스텁 감지 ($($py.Source)) — 실설치 진행" }
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  if ($LASTEXITCODE -ne 0) { throw "winget 설치 실패 (exit $LASTEXITCODE)" }
  Write-Host "   winget 설치 완료 — PATH 반영은 새 터미널부터"
  $script:StepStatus = 'PENDING_RESTART'
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
Write-Host "`n===== 단계 요약 (OK / PENDING_RESTART=새 터미널 필요 / MANUAL_REQUIRED=수동) =====" -ForegroundColor Green
foreach ($k in $report.Keys) { Write-Host ("  {0}: {1}" -f $k, $report[$k]) }

$diag = [ordered]@{
  'bun'    = if (Get-Command bun -ErrorAction SilentlyContinue) { "OK $(bun -v)" } else { 'X 새 터미널에서 재확인' }
  'python' = & {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py -and $py.Source -notlike '*WindowsApps*') { "OK $($py.Source)" }
    elseif ($py) { '! 스토어 스텁 — 새 터미널에서 재확인' } else { 'X 미설치' } }
  'claude' = & {
    $c = Get-Command claude -ErrorAction SilentlyContinue
    if ($c) { "OK $($c.Source)" }
    elseif (Test-Path "$HOME\.local\bin\claude.exe") { "OK $HOME\.local\bin\claude.exe (PATH 반영은 새 터미널부터)" }
    else { 'X 미설치 — irm https://claude.ai/install.ps1 | iex' } }
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
