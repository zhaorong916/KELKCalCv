@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title KELKCalCv - 首次部署引导

rem ============================================================
rem   KELKCalCv 一键首次部署
rem     a) 部署包模式: bootstrap.bat 在目标目录(如 D:\KELKCalCv\)
rem        -> 环境检查 -> 克隆仓库到当前目录 -> 生成 .env -> 启动
rem     b) 仓库内模式: bootstrap.bat 在 deploy\ 子目录
rem        -> 自动跳过克隆，仅检查/配置/启动
rem   详细说明见同目录《部署说明.md》
rem ============================================================

cd /d "%~dp0"

rem 检测是否在盘符根目录直接运行(如 D:\)，%~dp0.. 在根目录会解析错误
if "%~dp0"=="%~d0\" (
    echo [错误] 请不要在盘符根目录直接运行本脚本，例如 D:\ 或 E:\。
    echo        请将 bootstrap.bat 和部署说明.md 放入一个子目录后再运行，例如:
    echo          D:\KELKCalCv\bootstrap.bat
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

rem 模式 b: 当前位于仓库 deploy 目录(如 D:\KELKCalCv\deploy\)
if exist "%~dp0..\backend\app\main.py" (
    set "REPO_DIR=%~dp0..\"
    echo        检测到当前位于仓库 deploy 目录，跳过克隆
    goto :PRECHECK
)

where git >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Git，请先安装: https://git-scm.com/download/win
    pause
    exit /b 1
)

rem 模式 a: 当前目录已是 Git 仓库(如 D:\KELKCalCv\)
if exist "%~dp0.git" (
    echo        当前目录已是 Git 仓库，跳过克隆
    echo        日常更新请运行 deploy\update.bat
    set "REPO_DIR=%~dp0"
    goto :PRECHECK
)

rem 当前目录存在 backend\app\main.py 但无 .git: 可能是解压的源码包
if exist "%~dp0backend\app\main.py" (
    echo        检测到当前目录包含项目文件但非 Git 仓库
    echo        (可能是源码包解压，建议用 git clone 获取完整版本控制)
    set "USE_CURRENT="
    set /p USE_CURRENT=       输入 Y 使用当前目录，其他键退出并重新克隆:
    if /i not "!USE_CURRENT!"=="Y" (
        echo        已退出。请清空目录后重试，或手工执行 git clone。
        pause
        exit /b 1
    )
    set "REPO_DIR=%~dp0"
    goto :PRECHECK
)

rem 当前目录非空且非项目文件: 警告
dir /b "%~dp0" 2>nul | findstr /r /c:"." >nul
if not errorlevel 1 (
    echo        警告: 当前目录不为空:
    dir /b "%~dp0"
    echo.
    set "FORCE="
    set /p FORCE=       输入 Y 强制在此目录克隆，其他键退出:
    if /i not "!FORCE!"=="Y" (
        echo        已退出。请更换目录或清空后重试。
        pause
        exit /b 1
    )
)

echo        从 Gitee 克隆仓库到当前目录，私有仓库会提示输入账号/访问令牌 ...
git clone https://gitee.com/KELKzhao/kelkcalcv.git .
if errorlevel 1 (
    echo.
    echo [错误] 克隆失败。常见原因:
    echo          1. 网络无法访问 gitee.com
    echo          2. 私有仓库未输入正确的账号/个人访问令牌
    echo          3. 代理未配置，如需代理请执行: git config --global http.proxy http://host:port
    echo        请根据上方 git 报错信息处理后重试。
    pause
    exit /b 1
)

rem 二次校验:确认 .git 真实存在
if not exist "%~dp0.git" (
    echo [错误] 克隆命令返回成功但 .git 不存在，目录为空。
    echo        请检查 git 输出并手工排查。
    pause
    exit /b 1
)
set "REPO_DIR=%~dp0"

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
if exist "%REPO_DIR%backend\.env" (
    echo        backend\.env 已存在，保留现有配置
    goto :CONFIRM
)
if not exist "%REPO_DIR%backend\.env.example" (
    echo [错误] 未找到 "%REPO_DIR%backend\.env.example"，仓库可能不完整。
    pause
    exit /b 1
)
copy "%REPO_DIR%backend\.env.example" "%REPO_DIR%backend\.env" >nul
if errorlevel 1 (
    echo [错误] 生成 backend\.env 失败，请检查目录权限。
    pause
    exit /b 1
)
echo        已生成 backend\.env 占位符模板，请在打开的记事本中填写:
echo          DB_HOST / DB_USER / DB_PASSWORD / SECRET_KEY
notepad "%REPO_DIR%backend\.env"
echo        检测到记事本已关闭，继续...

:CONFIRM
echo.
echo [4/5] 启动确认
echo   仓库位置: %REPO_DIR%
set "CONFIRM="
set /p CONFIRM=  输入 Y 立即启动服务，其他键退出:
if /i not "%CONFIRM%"=="Y" (
    echo   已退出。稍后可运行:
    echo     "%REPO_DIR%deploy\start-server.bat"
    pause
    exit /b 0
)

echo.
echo [5/5] 启动服务 ...
call "%REPO_DIR%deploy\start-server.bat"

endlocal
