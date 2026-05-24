@echo off
setlocal
cd /d "%~dp0..\.."
title Baresto Manager — Update

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found in PATH.
  echo Install Python 3.12+ from https://www.python.org/downloads/windows/
  echo.
  pause
  exit /b 1
)

python "%~dp0baresto_updater.py"
set ERR=%ERRORLEVEL%
if not "%ERR%"=="0" pause
exit /b %ERR%
