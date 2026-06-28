# dev.ps1 - start all services for development with one command.
# Postgres runs in Docker; worker/API/bot run on the HOST so the BROWSER IS VISIBLE
# (set BROWSER_HEADLESS=false in .env).
#
# Run:  .\dev.ps1
# Stop: close the opened service windows (and: docker compose stop db)

$root = $PSScriptRoot

Write-Host "1/4  Postgres (Docker)..." -ForegroundColor Cyan
docker compose up -d db

Write-Host "2/4  Python worker (visible browser) on :8800..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "cd '$root\backend'; & '$root\.venv\Scripts\Activate.ps1'; uvicorn worker_app:app --port 8800"
)

Write-Host "3/4  Go API + site on :8000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command", "cd '$root\api'; go run ./cmd/server"
)

Write-Host "4/4  Telegram bot..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command", "cd '$root\api'; go run ./cmd/bot"
)

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Site:   http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Worker: http://127.0.0.1:8800/health" -ForegroundColor Green
Write-Host "Services opened in separate PowerShell windows." -ForegroundColor Green
