# Setup script for Zydrakon AI
$ErrorActionPreference = "Stop"

Write-Host "Setting up Zydrakon AI workspace..." -ForegroundColor Cyan

# 1. Python environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment in .venv..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

# 2. Frontend environment
if (Test-Path "frontend") {
    Write-Host "Installing frontend dependencies and building frontend..." -ForegroundColor Yellow
    Push-Location frontend
    try {
        & npm.cmd install
        & npm.cmd run build
    } finally {
        Pop-Location
    }
}

# 3. Create .env from .env.example if missing
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Write-Host "Creating default .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

Write-Host "Setup completed successfully! Run .\start.ps1 to start the application." -ForegroundColor Green
