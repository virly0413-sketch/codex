@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -c "import PIL, googleapiclient, google_auth_oauthlib, socks, openpyxl"
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe six_channel_start.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo 启动失败，请查看上方错误。
pause
exit /b 1
