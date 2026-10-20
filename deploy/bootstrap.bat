@echo off
chcp 65001 >nul
title KELKCalCv - 首次部署引导

rem ============================================================
rem   KELKCalCv 一键首次部署（双用途）
rem     a) 部署包根目录运行: 环境检查 -> 克隆仓库 -> 生成 .env -> 启动
rem     b) 仓库 deploy 目录运行: 自动跳过克隆，仅检查/配置/启动
rem   详细说明见同目录《部署说明.md》
rem ============================================================

setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   KELKCalCv - 首次部署引导
echo ============================================================
echo.

rem ----- [1/5] 定位/克隆仓库 -----
echo [1/5] 定位仓库 ...
set "REPO_DIR="
if exist "%~dp0..\backend\app\main.py" (
    set "REPO_DIR=%~dp0.."
    echo        检测到当前位于仓库 deploy 目录，跳过克隆
    goto :PRECHECK
)

where git >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Git，请先安装: https://git-scm.com/download/win
    pause
    exit /b 1
)
if exist "kelkcalcv\.git" (
    echo        目录 kelkcalcv 已存在，跳过克隆（日常更新请在仓库内运行 update.bat）
    set "REPO_DIR=%~dp0kelkcalcv"
    goto :PRECHECK
)
echo        从 Gitee 克隆仓库（私有仓库会提示输入账号/访问令牌）...
git clone https://gitee.com/KELKzhao/kelkcalcv.git
if errorlevel 1 (
    echo [错误] 克隆失败。检查网络后重试。
    pause
    exit /b 1
)
set "REPO_DIR=%~dp0kelkcalcv"

:PRECHECK
echo.
echo [2/5] 检查前置环境 ...
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请安装 3.10+ 并勾选 "Add Python to PATH"
    pause
    exit /b 1
)
python -c "import pyodbc" >nul 2>&1
if errorlevel 1 (
    echo [警告] pyodbc 不可用，可能缺少 ODBC Driver 17 for SQL Server
    echo        下载: https://learn.microsoft.com/zh-cn/sql/connect/odbc/download-odbc-driver-for-sql-server
) else (
    python -c "import pyodbc; d=[x for x in pyodbc.drivers() if 'SQL Server' in x]; print('       ODBC 驱动:', ','.join(d) if d else '未检测到 SQL Server 驱动!')"
)

:ENVCHECK
echo.
echo [3/5] 准备配置文件 backend\.env ...
if exist "%REPO_DIR%\backend\.env" (
    echo        backend\.env 已存在，保留现有配置
    goto :CONFIRM
)
copy "%REPO_DIR%\backend\.env.example" "%REPO_DIR%\backend\.env" >nul
echo        已生成 backend\.env（占位符模板），请在打开的记事本中填写:
echo          DB_HOST / DB_USER / DB_PASSWORD / SECRET_KEY
notepad "%REPO_DIR%\backend\.env"
echo        检测到记事本已关闭，继续...

:CONFIRM
echo.
echo [4/5] 启动确认
echo   仓库位置: %REPO_DIR%
set "CONFIRM="
set /p CONFIRM=  输入 Y 立即启动服务，其他键退出:
if /i not "%CONFIRM%"=="Y" (
    echo   已退出。稍后可运行:
    echo     %REPO_DIR%\deploy\start-server.bat
    pause
    exit /b 0
)

echo.
echo [5/5] 启动服务 ...
call "%REPO_DIR%\deploy\start-server.bat"

endlocal
