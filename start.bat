@echo off
REM One-click local start for Windows (cmd). Opens the API and the dashboard in two windows.
setlocal
cd /d "%~dp0backend"

if not exist ".venv" (
  echo [1/4] Creating Python virtual environment...
  python -m venv .venv || goto :err
)

echo [2/4] Installing Python packages - first time takes a minute...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || goto :err

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo  Created backend\.env  -  Notepad will open it now.
  echo    * Offline test : change  LLM_PROVIDER=anthropic  to  LLM_PROVIDER=mock
  echo    * Real test    : put your key after  ANTHROPIC_API_KEY=
  echo  Save the file, close Notepad, then run start.bat again.
  echo.
  notepad ".env"
  exit /b 0
)

echo [3/4] Starting the API on http://localhost:8000 ...
start "Scriptline API (keep open)" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

cd /d "%~dp0frontend"
if not exist "node_modules" (
  echo [4/4] Installing dashboard packages - first time takes a minute...
  call npm install --no-audit --no-fund || goto :err
)
echo [4/4] Starting the dashboard on http://localhost:3000 ...
start "Scriptline Dashboard (keep open)" cmd /k "npm run dev"

echo Opening your browser in a few seconds...
timeout /t 10 /nobreak >nul
start "" http://localhost:3000
exit /b 0

:err
echo.
echo Setup failed - read the error above, or paste it into the chat.
pause
exit /b 1
