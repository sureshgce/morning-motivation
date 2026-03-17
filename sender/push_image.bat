@echo off
:: ================================================================
::  Morning Motivation - Quick Image Push
::  
::  FOR THE SENDER (your colleague):
::  Drag-and-drop an image file onto this .bat to auto-commit & push.
::  Or run it and enter the image path when prompted.
::
::  Prerequisites:
::    - Git installed and on PATH
::    - Already cloned the repo locally
::    - Working directory is inside the cloned repo
:: ================================================================

setlocal EnableDelayedExpansion

set "IMAGES_DIR=images"

:: ── Get image path ──────────────────────────────────────────────
if "%~1"=="" (
    echo.
    echo  Drag-and-drop an image onto this script, or enter the path:
    echo.
    set /p "IMG_PATH=Image file path: "
) else (
    set "IMG_PATH=%~1"
)

:: ── Validate file ───────────────────────────────────────────────
if not exist "%IMG_PATH%" (
    echo ERROR: File not found: %IMG_PATH%
    pause
    exit /b 1
)

:: ── Get today's date for commit message ─────────────────────────
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set "DT=%%I"
set "TODAY=%DT:~0,4%-%DT:~4,2%-%DT:~6,2%"

:: ── Get file extension ──────────────────────────────────────────
set "EXT=%~x1"
if "%EXT%"=="" set "EXT=.jpg"

:: ── Copy to images folder with date name ────────────────────────
if not exist "%IMAGES_DIR%" mkdir "%IMAGES_DIR%"

set "DEST=%IMAGES_DIR%\%TODAY%%EXT%"
copy /y "%IMG_PATH%" "%DEST%" >nul
echo.
echo  Copied to: %DEST%

:: ── Git add, commit, push ───────────────────────────────────────
echo  Committing and pushing...
git add "%DEST%"
git commit -m "Morning motivation - %TODAY%"
git push

if errorlevel 1 (
    echo.
    echo ERROR: Git push failed. Check your remote configuration.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo    Pushed successfully!
echo    File: %DEST%
echo    Date: %TODAY%
echo  ============================================
echo.
timeout /t 3 >nul
