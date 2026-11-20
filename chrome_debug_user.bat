@echo off
chcp 65001 >nul
echo ==========================================
echo  Start Chrome with debug port 9222
echo  Profile: your default Chrome profile
echo  NOTE: close all Chrome windows first.
echo ==========================================
tasklist /FI "IMAGENAME eq chrome.exe" | find /I "chrome.exe" >nul
if not errorlevel 1 (
  echo.
  echo [!] Chrome is running. Please close Chrome completely, then run again.
  pause
  exit /b 1
)
start "" "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data" --no-first-run --no-default-browser-check
echo.
echo Chrome started. Keep it open, then run the agent.
timeout /t 3 >nul
