@echo off
chcp 65001 >nul
echo ==========================================
echo  Start Chrome with a dedicated agent profile
echo  Profile: .chrome-test
echo  URL: dianxiaobao ERP
echo ==========================================
start "" "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%~dp0.chrome-test" --no-first-run --no-default-browser-check "https://erp.dianxiaobao.net/"
echo.
echo Chrome started on port 9222. Keep this window open.
timeout /t 3 >nul
