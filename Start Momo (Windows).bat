@echo off
rem Double-click me to start Momo. The first run sets everything up (about a minute).
cd /d "%~dp0"
title Momo setup

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY goto nopython
%PY% -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>nul || goto nopython

if not exist ".venv\.momo-ready-2" (
  echo First run: setting up Momo ^(about a minute^)...
  if exist ".venv" rmdir /s /q ".venv"
  %PY% -m venv .venv || goto fail
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip || goto fail
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto fail
  echo ok> ".venv\.momo-ready-2"
)

start "" ".venv\Scripts\pythonw.exe" run.py
exit /b 0

:nopython
echo.
echo  Momo needs Python 3.10 or newer.
echo  1. Download it from https://www.python.org/downloads/
echo  2. In the installer, TICK "Add python.exe to PATH", then Install.
echo  3. Double-click "Start Momo (Windows)" again.
echo.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:fail
echo.
echo  Setup failed. Scroll up for the error, or send a screenshot.
pause
exit /b 1
