﻿@echo off
chcp 65001 >nul
title KELKCalCv Server

rem ============================================================
rem   KELKCalCv - 生产/服务器环境启动
rem   - 清理端口 8000
rem   - 启动 FastAPI (uvicorn) + 静态前端
rem   - 浏览器访问 http://localhost:8000
rem ============================================================

setlocal
rem 本脚本位于 deploy\ 子目录, backend 在其上一级
cd /d "%~dp0..\backend" || (
    echo [错误] 无法进入 backend 目录, 请确认仓库文件完整.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   KELKCalCv 启动中 ...
echo ============================================================
echo.

rem ----- Step 1: 清理端口 8000 -----
echo [1/3] 清理端口 8000 ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo        终止 PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

rem ----- Step 2: 检查 Python -----
echo [2/3] 检查 Python 与依赖 ...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请安装 Python 3.10+
    pause
    exit /b 1
)
if not exist "venv\Scripts\activate.bat" (
    echo        未检测到 venv，创建虚拟环境 ...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt -q
) else (
    call venv\Scripts\activate.bat
    echo        venv 已就绪
)

rem ----- Step 3: 启动服务 -----
echo.
echo [3/3] 启动服务器 ...
echo.
echo   访问地址: http://localhost:8000
echo   接口文档: http://localhost:8000/docs
echo   按 Ctrl+C 停止服务
echo.

start "" http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

endlocal
