@echo off
title Push FNHRIP to GitHub
setlocal

echo ================================================
echo FNHRIP - GitHub Push
echo ================================================

git --version >nul 2>&1
if errorlevel 1 (
  echo Git is not installed or not available on PATH.
  pause
  exit /b 1
)

if not exist .git (
  git init
)

if not exist .gitignore (
  echo .gitignore is missing. Aborting.
  pause
  exit /b 1
)

git add .
git status

echo.
echo Review the files above. Confirm that no .env, database, password, or secret file is staged.
echo.
set /p CONFIRM=Continue with commit and push? (Y/N):
if /I not "%CONFIRM%"=="Y" exit /b 0

git commit -m "Prepare FNHRIP for GitHub"
git branch -M main

git remote -v

git push -u origin main

pause
