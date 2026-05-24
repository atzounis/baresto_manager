@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0..\.."
title Baresto Manager — Firewall rule

set PORT=8765
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    set "KEY=%%A"
    set "VAL=%%B"
    if /i "!KEY!"=="DJANGO_PORT" set PORT=!VAL!
  )
)

set "RULE_NAME=Baresto Manager (TCP %PORT%)"

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator access to add the firewall rule...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b 0
)

netsh advfirewall firewall show rule name="%RULE_NAME%" >nul 2>&1
if not errorlevel 1 (
  echo Firewall rule already exists: %RULE_NAME%
  goto :done
)

echo Adding inbound rule for TCP port %PORT% on private networks...
netsh advfirewall firewall add rule name="%RULE_NAME%" dir=in action=allow protocol=TCP localport=%PORT% profile=private enable=yes
if errorlevel 1 (
  echo ERROR: Could not add firewall rule.
  pause
  exit /b 1
)

echo Done. Phones on the same Wi-Fi can connect to port %PORT%.

:done
timeout /t 3 >nul
exit /b 0
