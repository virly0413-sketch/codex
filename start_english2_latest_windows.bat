@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe english2_latest_start.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo Failed. Please read the error above and ENGLISH2_LATEST_GUIDE.md.
pause
exit /b 1
