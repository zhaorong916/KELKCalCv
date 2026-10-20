@echo off
chcp 65001 >nul
title KELKCalCv - 远程更新

rem ============================================================
rem   KELKCalCv - 从 Gitee 远程拉取最新代码并更新依赖
rem   服务器本地 backend/.env 不会被覆盖（.gitignore 已排除）
rem   执行完后需手动 start-server.bat 或重启服务
rem ============================================================

setlocal
cd /d "%~dp0\.."

echo.
echo ============================================================
echo   KELKCalCv - 远程更新
echo ============================================================
echo.

rem ----- Step 1: Git 拉取最新代码 -----
echo [1/3] 从 Gitee 远程拉取最新代码 ...
git pull origin main
if errorlevel 1 (
    echo [错误] git pull 失败。检查网络连接或远程仓库地址。
    pause
    exit /b 1
)

rem ----- Step 2: 更新 Python 依赖 -----
echo.
echo [2/3] 更新 Python 依赖 ...
cd backend
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [警告] 依赖更新失败。可稍后手动执行: pip install -r requirements.txt
) else (
    echo        依赖已同步完成。
)

rem ----- Step 3: 状态提示 -----
echo.
echo ============================================================
echo   更新完成
echo ============================================================
echo.
echo   代码来源: https://gitee.com/KELKzhao/kelkcalcv
echo   服务器配置: backend\.env  (不受 git 覆盖)
echo.
echo   下一步:
echo     1. 停止当前服务 (如有运行)
echo     2. 运行 deploy\start-server.bat 重启
echo.
pause
endlocal
