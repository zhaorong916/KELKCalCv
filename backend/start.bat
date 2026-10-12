@echo off
title KELKCalCv Server
echo ========================================
echo   KELKCalCv Cv Calculation and Noise Analysis
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Kill old process on port 8000
echo [1/3] Cleaning old process ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM Install dependencies
echo [2/3] Installing Python dependencies ...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Dependencies install failed.
    pause
    exit /b 1
)

REM Check ODBC Driver
echo [3/3] Checking ODBC Driver 17 for SQL Server ...
python -c "import pyodbc; print([d for d in pyodbc.drivers() if 'SQL Server' in d])"
if errorlevel 1 (
    echo [WARNING] pyodbc import failed. Check ODBC Driver installation.
)

REM Start server
echo.
echo Starting server on port 8000 ...
echo URL : http://localhost:8000
echo API : http://localhost:8000/docs
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
