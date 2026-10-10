# One-command local start (Windows PowerShell): API on :8000, dashboard on :3000.
# If scripts are blocked:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location "$Root\backend"
if (-not (Test-Path ".venv")) { Write-Host "-> creating Python virtualenv"; python -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "!! Created backend\.env - put your ANTHROPIC_API_KEY in it, then re-run .\start.ps1"
  exit 1
}
Write-Host "-> starting API on http://localhost:8000"
$api = Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","app.main:app","--port","8000" -PassThru -NoNewWindow

try {
  Set-Location "$Root\frontend"
  if (-not (Test-Path "node_modules")) { npm install --no-audit --no-fund }
  Write-Host "-> starting dashboard on http://localhost:3000"
  npm run dev
} finally {
  Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
}
