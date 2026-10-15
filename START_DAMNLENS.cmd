@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" setup_judges.py %*
  goto finish
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 setup_judges.py %*
  goto finish
)
where python >nul 2>nul
if not errorlevel 1 (
  python setup_judges.py %*
  goto finish
)
echo Install 64-bit Python 3.12 from https://www.python.org/downloads/
echo Select Add Python to PATH, reopen this folder, and try again.
exit /b 1
:finish
set "damnlensExit=%errorlevel%"
if not "%damnlensExit%"=="0" (
  echo.
  echo Setup or launch failed. Copy the message above when reporting a problem.
  if "%~1"=="" pause
)
exit /b %damnlensExit%
