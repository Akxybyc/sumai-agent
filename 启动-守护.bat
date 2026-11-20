@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo  Sumai Agent 守护启动（崩溃自动重启）
echo  关闭此窗口即停止服务
echo  日志: data\server.log
echo ==========================================
".venv\Scripts\python.exe" "server\supervise.py"
pause
