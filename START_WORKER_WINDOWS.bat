@echo off
setlocal
cd /d "%~dp0"
title PT Mulia Hakimaco Sejahtera - Background Worker
if not exist ".venv\Scripts\python.exe" (
 echo Jalankan START_WINDOWS.bat terlebih dahulu.
 pause
 exit /b 1
)
set "MHS_MODE=demo"
echo Local worker running. Keep this window open.
".venv\Scripts\python.exe" -m backend.app.worker
pause
