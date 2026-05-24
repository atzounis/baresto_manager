@echo off
REM Convenience wrapper — run the Windows updater from the project root.
cd /d "%~dp0"
call scripts\windows\Update-BarestoManager.bat
