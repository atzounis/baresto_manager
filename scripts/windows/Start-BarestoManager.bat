@echo off
setlocal
cd /d "%~dp0..\.."
title Baresto Manager

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found in PATH.
  echo The launcher will try to install Python 3.12 via winget, or open python.org.
  echo.
)

python "%~dp0baresto_launcher.py"
set ERR=%ERRORLEVEL%
if not "%ERR%"=="0" pause
exit /b %ERR%
