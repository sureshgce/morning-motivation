@echo off
:: ================================================================
::  Morning Momentum Bot - BUILD EXE
::
::  This script builds the standalone .exe using PyInstaller.
::  Requires Python + venv (only on the BUILD machine).
::  The resulting exe needs NO Python on the target machine.
::
::  Output: dist\morning_bot\morning_bot.exe
:: ================================================================

setlocal EnableDelayedExpansion

set "SETUP_DIR=%~dp0"
set "VENV_DIR=%SETUP_DIR%venv"

echo.
echo  ============================================
echo    Morning Momentum Bot - Build EXE
echo  ============================================
echo.

:: ── Step 1: Check Python ────────────────────────────────────────
echo [1/4] Checking Python installation...

:: Try system Python first
set "PYTHON_CMD="
where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :found_python
)

:: Try DevDelProject venv
if exist "c:\DevDelProject\venv\Scripts\python.exe" (
    set "PYTHON_CMD=c:\DevDelProject\venv\Scripts\python.exe"
    goto :found_python
)

:: Try py launcher
where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto :found_python
)

echo ERROR: Python is not found on this build machine.
echo        Install Python 3.9+ to build the exe.
pause
exit /b 1

:found_python
echo        Found: %PYTHON_CMD%

:: ── Step 2: Create venv ─────────────────────────────────────────
echo.
echo [2/4] Setting up build environment...
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)
call "%VENV_DIR%\Scripts\activate.bat"
echo        venv activated

:: ── Step 3: Install dependencies ────────────────────────────────
echo.
echo [3/4] Installing dependencies...
pip install --upgrade pip >nul 2>&1
pip install -r "%SETUP_DIR%requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

:: ── Step 4: Build exe ───────────────────────────────────────────
echo.
echo [4/4] Building standalone exe with PyInstaller...
cd /d "%SETUP_DIR%"
pyinstaller --clean morning_bot.spec

if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

:: ── Copy config.json to dist ────────────────────────────────────
copy /y "%SETUP_DIR%config.json" "%SETUP_DIR%dist\morning_bot\config.json" >nul

echo.
echo  ============================================
echo    Build Complete!
echo  ============================================
echo.
echo  EXE location:
echo    %SETUP_DIR%dist\morning_bot\morning_bot.exe
echo.
echo  To deploy to another PC, copy the entire
echo    dist\morning_bot\ folder.
echo.
echo  Files to include when distributing:
echo    dist\morning_bot\       (entire folder)
echo    setup.bat               (one-time setup)
echo    start_bot.bat           (manual start)
echo    stop_bot.bat            (manual stop)
echo.
pause
