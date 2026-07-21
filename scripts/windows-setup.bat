@echo off
title ThisCode Windows Setup Kit
echo.
echo  ThisCode Windows setup — starting (no admin needed)...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/treylom/ThisCode/main/scripts/windows-setup.ps1 | iex"
echo.
if %ERRORLEVEL% NEQ 0 (
  echo  WARNING: setup script exited with code %ERRORLEVEL%. Check messages above.
) else (
  echo  Setup attempt finished. Review the diagnosis table above.
)
echo  Next: OPEN A NEW TERMINAL so PATH/policy changes apply.
echo.
pause
