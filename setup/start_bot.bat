@echo off
:: ================================================================
::  Morning Momentum Bot - START
::  Launches the bot (no Python required — runs the exe)
:: ================================================================

setlocal EnableDelayedExpansion

set "SETUP_DIR=%~dp0"

:: ── Locate the exe ──────────────────────────────────────────────
set "BOT_EXE="

if exist "%SETUP_DIR%dist\morning_bot\morning_bot.exe" (
    set "BOT_EXE=%SETUP_DIR%dist\morning_bot\morning_bot.exe"
    set "BOT_DIR=%SETUP_DIR%dist\morning_bot"
    goto :found
)
if exist "%SETUP_DIR%morning_bot.exe" (
    set "BOT_EXE=%SETUP_DIR%morning_bot.exe"
    set "BOT_DIR=%SETUP_DIR%"
    goto :found
)

echo ERROR: morning_bot.exe not found.
echo        Run build_exe.bat first, or run setup.bat.
pause
exit /b 1

:found

:: ── Check if already running ────────────────────────────────────
if exist "%BOT_DIR%\.bot.pid" (
    set /p PID=<"%BOT_DIR%\.bot.pid"
    tasklist /fi "PID eq !PID!" 2>nul | findstr /i "morning_bot" >nul
    if not errorlevel 1 (
        echo Bot is already running (PID: !PID!).
        echo Right-click the tray icon to interact.
        pause
        exit /b 0
    ) else (
        echo Stale PID file found — cleaning up.
        del "%BOT_DIR%\.bot.pid" >nul 2>&1
    )
)

:: ── Launch ──────────────────────────────────────────────────────
echo Starting Morning Momentum Bot...
start "" "%BOT_EXE%"

echo.
echo  Bot is running in the system tray (sun icon).
echo  Right-click the tray icon for options.
echo.
timeout /t 3 >nul
