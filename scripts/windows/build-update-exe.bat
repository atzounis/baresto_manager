@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo Building BarestoUpdate.exe ...
echo Run this script on Windows from the extracted project folder.
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3.12+ is required to build the executable.
  echo Install from https://www.python.org/downloads/windows/ with "Add to PATH" enabled.
  pause
  exit /b 1
)

python -m pip install --upgrade pip pyinstaller>=6.0
if errorlevel 1 (
  echo ERROR: Could not install PyInstaller.
  pause
  exit /b 1
)

python -m PyInstaller ^
  --onefile ^
  --console ^
  --name BarestoUpdate ^
  --clean ^
  --noconfirm ^
  --hidden-import baresto_launcher ^
  baresto_updater.py

if errorlevel 1 (
  echo ERROR: PyInstaller build failed.
  pause
  exit /b 1
)

copy /Y "dist\BarestoUpdate.exe" "..\..\BarestoUpdate.exe" >nul
echo.
echo Done: BarestoUpdate.exe copied to project root.
echo Double-click BarestoUpdate.exe next to manage.py to download updates and run migrations.
echo.
pause
