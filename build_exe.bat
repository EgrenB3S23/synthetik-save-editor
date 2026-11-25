@echo off
cd /d "%~dp0"
echo This builds the exe on this PC from the Python scripts in this folder.
echo PyInstaller, from PyPI, only packs the Python interpreter with those scripts.
echo.

set "PY="
where py >nul 2>&1
if %errorlevel%==0 (
  for /f "usebackq delims=" %%P in (`py -3 -c "import sys; print(sys.executable)"`) do set "PY=%%P"
)
if not defined PY (
  for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ensure_python.ps1" -Which python`) do set "PY=%%P"
)
if not defined PY (
  echo Could not set up Python.
  exit /b 1
)

"%PY%" -c "import PyInstaller" 1>nul 2>nul
if errorlevel 1 (
  echo PyInstaller is not installed. Installing it with pip...
  "%PY%" -m pip install pyinstaller
  if errorlevel 1 exit /b 1
)

"%PY%" -m PyInstaller --noconfirm --clean synthetik-save-editor.spec
if errorlevel 1 exit /b 1
"%PY%" -m PyInstaller --noconfirm --clean synthetik-save-editor-cli.spec
if errorlevel 1 exit /b 1

echo.
echo Window:  dist\synthetik-save-editor.exe
echo Text menu: dist\synthetik-save-editor-cli.exe
