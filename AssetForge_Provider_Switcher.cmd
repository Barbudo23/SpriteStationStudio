@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo AssetForge virtual environment was not found.
  echo Run setup first, then open this switcher again.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m assetforge --provider-menu
echo.
pause
