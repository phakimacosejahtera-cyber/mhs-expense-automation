@echo off
setlocal
cd /d "%~dp0"
title PT Mulia Hakimaco Sejahtera - Expense Automation
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
echo [1/3] Checking Python...
%PY% --version || (echo Python tidak ditemukan. Install Python 3.11+ dari https://www.python.org/downloads/windows/ & pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" (
  echo [2/3] Creating Python virtual environment...
  %PY% -m venv .venv || (pause & exit /b 1)
)
echo [2/3] Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt || (echo Instalasi gagal. Periksa koneksi internet dan versi Python. & pause & exit /b 1)
echo [3/3] Starting the local app...
set "MHS_MODE=demo"
echo.
echo Open this URL in your browser: http://127.0.0.1:8000
echo WARNING: DEMO LOCAL ONLY. Do not expose port 8000 to the internet.
echo Press CTRL+C to stop.
echo.
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
pause
