@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "LOG=启动日志.txt"
echo Six-channel publisher startup > "%LOG%"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv >> "%LOG%" 2>&1
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -c "import PIL, googleapiclient, google_auth_oauthlib, socks, openpyxl" >> "%LOG%" 2>&1
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt >> "%LOG%" 2>&1
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -u six_channel_start.py >> "%LOG%" 2>&1
if errorlevel 1 goto fail
echo 程序已关闭。启动日志保存在“启动日志.txt”。
pause
exit /b 0
:fail
echo 启动失败。请打开同目录的“启动日志.txt”查看具体原因。
type "%LOG%"
pause
exit /b 1
