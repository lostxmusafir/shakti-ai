# Startup script for Zydrakon AI
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Error "Virtual environment not found. Please run .\setup.ps1 first."
    exit 1
}

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Write-Host "Creating default .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

$env:PYTHONPATH = "backend"

Write-Host "Starting Zydrakon AI server at http://127.0.0.1:8000..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray

& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
