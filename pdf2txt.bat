@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0ensure-env.bat"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" pdf2txt.py --first --format txt
echo.
pause
endlocal
