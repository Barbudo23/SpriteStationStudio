@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo AssetForge: локальное Python-окружение не найдено.
  echo Требуется настроить проект перед первым запуском.
  pause
  exit /b 1
)

:menu
cls
echo ========================================
echo          AssetForge — главное меню
echo ========================================
echo 1. Показать текущее состояние проекта
echo 2. Показать план 10 итераций
echo 3. Выбрать AI-провайдера
echo 4. Показать активного AI-провайдера
echo 0. Выход
echo.
set /p "choice=Выберите пункт: "

if "%choice%"=="1" goto status
if "%choice%"=="2" goto plan
if "%choice%"=="3" goto provider
if "%choice%"=="4" goto show_provider
if "%choice%"=="0" exit /b 0

echo.
echo Неизвестный пункт. Введите 0, 1, 2, 3 или 4.
pause
goto menu

:status
echo.
".venv\Scripts\python.exe" -m assetforge.runner --project-root projects/Soldier_AK47 --status
pause
goto menu

:plan
echo.
".venv\Scripts\python.exe" -m assetforge.runner --project-root projects/Soldier_AK47 --plan
pause
goto menu

:provider
echo.
".venv\Scripts\python.exe" -m assetforge.runner --provider-menu
pause
goto menu

:show_provider
echo.
".venv\Scripts\python.exe" -m assetforge.runner --show-provider
pause
goto menu
