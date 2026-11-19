@echo off
setlocal
cd /d "%~dp0"
title PT Mulia Hakimaco Sejahtera - Test Suite
if not exist ".venv\Scripts\python.exe" (
 echo Jalankan START_WINDOWS.bat terlebih dahulu.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r backend\requirements-dev.txt || (pause & exit /b 1)
".venv\Scripts\python.exe" -m pytest -q tests
if errorlevel 1 (echo TEST GAGAL.) else (echo Semua test selesai dengan sukses.)
pause
