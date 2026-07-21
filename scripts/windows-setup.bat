@echo off
title ThisCode Windows Setup Kit
echo.
echo  ThisCode Windows setup — starting (no admin needed)...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/treylom/ThisCode/main/scripts/windows-setup.ps1 | iex"
echo.
echo  Done. Review the diagnosis table above, then OPEN A NEW TERMINAL.
echo.
pause
