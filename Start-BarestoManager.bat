@echo off
REM Convenience wrapper — runs the Windows launcher from the project root.
cd /d "%~dp0"
call scripts\windows\Start-BarestoManager.bat
