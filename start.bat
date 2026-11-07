@echo off
setlocal enabledelayedexpansion
title Zydrakon AI - Company Data Assistant

cd /d "%~dp0"

echo ========================================================
echo        Zydrakon AI - Company Data Assistant
echo ========================================================
echo.

:: 1. Check Python virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [!] Virtual environment not found in .venv.
    echo [*] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Python not found or venv creation failed.
        pause
        exit /b 1
    )
    echo [*] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

:: 2. Check .env configuration
if not exist ".env" (
    if exist ".env.example" (
        echo [*] Creating .env from .env.example...
        copy ".env.example" ".env" >nul
    )
)

:: 3. Check frontend production build
if not exist "frontend\dist\index.html" (
    echo [*] Building frontend bundle...
    cd frontend
    call npm.cmd install
    call npm.cmd run build
    cd ..
)

:: 4. Start backend server (serves both API and React frontend)
set "PYTHONPATH=backend"

echo.
echo [*] Starting server at http://127.0.0.1:8000 ...
echo [*] Opening browser...
start "" "http://127.0.0.1:8000"

echo [*] Server is running. Press Ctrl+C to stop.
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
