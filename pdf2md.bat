@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv\Scripts\python.exe
  pause
  exit /b 1
)

".venv\Scripts\python.exe" pdf2txt.py --first --format md
echo.
pause
endlocal
