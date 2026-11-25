@echo off
cd /d "%~dp0"
where pyw >nul 2>&1
if %errorlevel%==0 (
  start "" pyw "%~dp0editor.pyw" %*
  exit /b 0
)
where pythonw >nul 2>&1
if %errorlevel%==0 (
  start "" pythonw "%~dp0editor.pyw" %*
  exit /b 0
)

set "PYW="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ensure_python.ps1" -Which pythonw`) do set "PYW=%%P"
if not defined PYW (
  echo Could not set up Python.
  pause
  exit /b 1
)
start "" "%PYW%" "%~dp0editor.pyw" %*
