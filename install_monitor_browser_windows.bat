@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.download.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto fail
echo Browser installed. Run start_monitor_windows.bat again.
pause
exit /b 0
:fail
echo Installation failed. Check your network or select an existing Chrome/Edge EXE in the program.
pause
exit /b 1
