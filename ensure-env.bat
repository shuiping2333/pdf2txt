@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" exit /b 0

echo First run: installing Python packages. This can take several minutes.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m venv .venv
) else (
  python -m venv .venv
)
if errorlevel 1 (
  echo Install Python 3.12 or newer from https://www.python.org/downloads/
  echo During setup, check "Add python.exe to PATH".
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Package install failed. Check the network and run this file again.
  pause
  exit /b 1
)

exit /b 0
