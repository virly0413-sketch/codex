@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.download.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe baidu_desktop.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo Failed. Please read BAIDU_GUIDE.md and the error above.
pause
exit /b 1
