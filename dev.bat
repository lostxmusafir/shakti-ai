@echo off
title Zydrakon AI - Full Development Mode (FastAPI + Vite)

cd /d "%~dp0"

echo ========================================================
echo   Zydrakon AI - Development Mode (Backend + Frontend)
echo ========================================================
echo.

set "PYTHONPATH=backend"

echo [*] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "Zydrakon Backend" cmd /k "cd /d "%~dp0" && set PYTHONPATH=backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [*] Starting Vite Frontend on http://127.0.0.1:5173 ...
start "Zydrakon Frontend" cmd /k "cd /d "%~dp0\frontend" && npm.cmd run dev"

echo.
echo Both services started in separate windows.
echo Frontend: http://127.0.0.1:5173
echo Backend:  http://127.0.0.1:8000
echo.
