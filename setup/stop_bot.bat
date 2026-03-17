@echo off
:: ================================================================
::  Morning Momentum Bot - STOP
::  Gracefully stops the running bot process
:: ================================================================

setlocal EnableDelayedExpansion

set "SETUP_DIR=%~dp0"

:: ── Try PID file in dist location first, then current dir ───────
set "PID_FILE="
if exist "%SETUP_DIR%dist\morning_bot\.bot.pid" (
    set "PID_FILE=%SETUP_DIR%dist\morning_bot\.bot.pid"
) else if exist "%SETUP_DIR%.bot.pid" (
    set "PID_FILE=%SETUP_DIR%.bot.pid"
)

if not defined PID_FILE (
    echo Bot does not appear to be running (no PID file).
    echo.
    echo Checking for any morning_bot processes...
    taskkill /im morning_bot.exe /f >nul 2>&1
    if not errorlevel 1 (
        echo Terminated morning_bot.exe processes.
    ) else (
        echo No morning_bot.exe processes found.
    )
    pause
    exit /b 0
)

set /p PID=<"%PID_FILE%"
echo Stopping Morning Momentum Bot (PID: %PID%)...

taskkill /pid %PID% /f >nul 2>&1

if errorlevel 1 (
    echo Process %PID% was not running.
    :: Try by name as fallback
    taskkill /im morning_bot.exe /f >nul 2>&1
) else (
    echo Process %PID% terminated.
)

:: Clean up PID file
del "%PID_FILE%" >nul 2>&1

echo.
echo  Bot stopped.
echo.
timeout /t 2 >nul
