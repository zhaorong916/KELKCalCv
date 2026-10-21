@echo off
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
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败.
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat
python -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo        安装依赖 ...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败, 请检查网络或代理后重试.
        pause
        exit /b 1
    )
) else (
    echo        venv 已就绪
)

rem ----- Step 3: 防火墙放行 8000 -----
echo [3/4] 配置防火墙放行 8000 端口 ...
netsh advfirewall firewall show rule name="KELKCalCv 8000" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="KELKCalCv 8000" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
    if errorlevel 1 (
        echo [警告] 防火墙规则添加失败. 请以管理员身份运行:
        echo          netsh advfirewall firewall add rule name="KELKCalCv 8000" dir=in action=allow protocol=TCP localport=8000
    ) else (
        echo        已添加入站规则 KELKCalCv 8000
    )
) else (
    echo        防火墙规则已存在, 跳过
)

rem ----- Step 4: 启动服务 -----
echo.
echo [4/4] 启动服务器 ...
echo.
echo   访问地址: http://localhost:8000
echo   接口文档: http://localhost:8000/docs
echo   按 Ctrl+C 停止服务
echo.

start "" http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

endlocal
