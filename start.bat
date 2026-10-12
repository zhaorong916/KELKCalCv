@echo off
title KELKCalCv Dev Launcher

rem ===============================================================
rem   KELKCalCv - One-click Dev Environment Launcher (single window)
rem   - Clear port 8000
rem   - Start backend (FastAPI + uvicorn) on 8000, serves frontend from static
rem   - Open browser http://localhost:8000
rem   Pure ASCII only - no codepage dependency
rem ===============================================================

setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   KELKCalCv - Dev Launcher
echo ============================================================
echo.

rem ----- Step 1: kill processes on port 8000 -----
echo [1/3] Cleaning port 8000 ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo        Killing PID %%a on port 8000
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

rem ----- Step 2: install dependencies -----
echo [2/3] Checking Python dependencies ...
cd /d "%~dp0backend"
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Dependencies install failed. Check network or pip config.
    pause
    exit /b 1
)

rem ----- Step 3: start backend -----
echo [3/3] Starting server on port 8000 ...
echo.
echo   URL      : http://localhost:8000
echo   API docs : http://localhost:8000/docs
echo.
echo   Press Ctrl+C to stop the server.
echo.

start "" http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

endlocal
