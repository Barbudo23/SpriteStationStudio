@echo off
setlocal
cd /d "%~dp0"
echo Starting Pseudo3D Forge 0.1.1...
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 run.py
) else (
    python run.py
)
if errorlevel 1 pause
