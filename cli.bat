@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py main.py %*
  exit /b %errorlevel%
)

set "PY="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ensure_python.ps1" -Which python`) do set "PY=%%P"
if not defined PY (
  echo Could not set up Python.
  pause
  exit /b 1
)
"%PY%" "%~dp0main.py" %*
