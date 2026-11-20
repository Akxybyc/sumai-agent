@echo off
chcp 65001 >nul
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set NO_PROXY=127.0.0.1,localhost
set no_proxy=127.0.0.1,localhost
cd /d "%~dp0server"
echo ==========================================
echo  Sumai Agent backend  http://127.0.0.1:8000
echo  Keep this window open while working.
echo ==========================================
"%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
