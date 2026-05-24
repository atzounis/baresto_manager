@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo Building BarestoManager.exe ...
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
  --name BarestoManager ^
  --clean ^
  --noconfirm ^
  baresto_launcher.py

if errorlevel 1 (
  echo ERROR: PyInstaller build failed.
  pause
  exit /b 1
)

copy /Y "dist\BarestoManager.exe" "..\..\BarestoManager.exe" >nul
echo.
echo Done: BarestoManager.exe copied to project root.
echo Double-click BarestoManager.exe next to manage.py to start the app.
echo.
pause
