@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title KELKCalCv - 首次部署引导

rem ============================================================
rem   KELKCalCv 一键首次部署(双用途)
rem     a) 部署包根目录运行: 环境检查 -> 克隆仓库 -> 生成 .env -> 启动
rem     b) 仓库 deploy 目录运行: 自动跳过克隆，仅检查/配置/启动
rem   详细说明见同目录《部署说明.md》
rem ============================================================

cd /d "%~dp0"

rem 检测是否在盘符根目录直接运行（如 D:\），%~dp0.. 在根目录会解析错误
if "%~dp0"=="%~d0\" (
    echo [错误] 请不要在盘符根目录（如 D:\）直接运行本脚本。
    echo        请将 bootstrap.bat 和部署说明.md 放入一个子目录后再运行，例如:
    echo          D:\KELK-deploy\bootstrap.bat
    echo        或在仓库内运行 kelkcalcv\deploy\start-server.bat
    pause
    exit /b 1
)

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

rem 已存在完整仓库:跳过克隆
if exist "%~dp0kelkcalcv\.git" (
    echo        目录 kelkcalcv 已是 Git 仓库，跳过克隆
    echo        (日常更新请运行 kelkcalcv\deploy\update.bat)
    set "REPO_DIR=%~dp0kelkcalcv"
    goto :PRECHECK
)

rem 目录存在但非 Git 仓库(空目录或上次克隆中断的残留):清理后重克隆
if exist "%~dp0kelkcalcv" (
    echo        检测到 kelkcalcv 目录已存在但不是 Git 仓库
    echo        (可能为空目录或上次克隆中断的残留)
    set "CLEAN="
    set /p CLEAN=       输入 Y 删除该目录并重新克隆，其他键退出:
    if /i not "!CLEAN!"=="Y" (
        echo        已退出。请手工处理 kelkcalcv 目录后重试。
        pause
        exit /b 1
    )
    rmdir /s /q "%~dp0kelkcalcv"
    if errorlevel 1 (
        echo [错误] 无法删除 kelkcalcv 目录，可能被占用。请关闭占用程序后重试。
        pause
        exit /b 1
    )
)

echo        从 Gitee 克隆仓库(私有仓库会提示输入账号/访问令牌)...
git clone https://gitee.com/KELKzhao/kelkcalcv.git "%~dp0kelkcalcv"
if errorlevel 1 (
    echo.
    echo [错误] 克隆失败。常见原因:
    echo          1. 网络无法访问 gitee.com
    echo          2. 私有仓库未输入正确的账号/个人访问令牌
    echo          3. 代理未配置(如需代理: git config --global http.proxy http://host:port)
    echo        请根据上方 git 报错信息处理后重试。
    rem 清理克隆失败可能留下的空目录
    if exist "%~dp0kelkcalcv\.git" (
        echo        克隆部分完成，保留现有目录。
    ) else (
        if exist "%~dp0kelkcalcv" rmdir /s /q "%~dp0kelkcalcv" >nul 2>&1
    )
    pause
    exit /b 1
)

rem 二次校验:确认 .git 真实存在
if not exist "%~dp0kelkcalcv\.git" (
    echo [错误] 克隆命令返回成功但 kelkcalcv\.git 不存在，目录为空。
    echo        请检查 git 输出并手工排查。
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

echo.
echo [3/5] 准备配置文件 backend\.env ...
if exist "%REPO_DIR%\backend\.env" (
    echo        backend\.env 已存在，保留现有配置
    goto :CONFIRM
)
if not exist "%REPO_DIR%\backend\.env.example" (
    echo [错误] 未找到 "%REPO_DIR%\backend\.env.example"，仓库可能不完整。
    pause
    exit /b 1
)
copy "%REPO_DIR%\backend\.env.example" "%REPO_DIR%\backend\.env" >nul
if errorlevel 1 (
    echo [错误] 生成 backend\.env 失败，请检查目录权限。
    pause
    exit /b 1
)
echo        已生成 backend\.env(占位符模板)，请在打开的记事本中填写:
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
    echo     "%REPO_DIR%\deploy\start-server.bat"
    pause
    exit /b 0
)

echo.
echo [5/5] 启动服务 ...
call "%REPO_DIR%\deploy\start-server.bat"

endlocal
