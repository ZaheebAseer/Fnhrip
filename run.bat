@echo off
setlocal
title FNHRIP Local Development Server

echo ===============================================================
echo Starting Federated National Health Resource Intelligence Platform
echo ===============================================================

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

set "PYTHON_EXE=.venv\Scripts\python.exe"

echo Installing/updating dependencies...
%PYTHON_EXE% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)

echo Seeding local database...
%PYTHON_EXE% -m backend.seed_data
if errorlevel 1 (
  echo Database seeding failed. Check your .env configuration.
  pause
  exit /b 1
)

echo Launching FNHRIP Server on http://localhost:5000...
start "" "http://localhost:5000/login.html"
%PYTHON_EXE% -m backend.app

pause
