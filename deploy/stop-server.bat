@echo off
chcp 65001 >nul
title KELKCalCv - 停止服务

rem 终止所有监听 8000 端口的进程

setlocal
echo.
echo 正在停止 KELKCalCv 服务 ...
echo.
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo   终止 PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
echo.
echo 完成。
timeout /t 1 /nobreak >nul
endlocal
