@echo off
:: ================================================================
::  Morning Momentum Bot - ONE-TIME SETUP
::
::  No Python required! This sets up the bot using the pre-built exe.
::  It registers a Windows Scheduled Task so the bot auto-starts
::  at every logon.
::
::  Run this ONCE after copying the files to the target PC.
:: ================================================================

setlocal EnableDelayedExpansion

set "SETUP_DIR=%~dp0"
set "TASK_NAME=MorningMomentumBot"

:: ── Locate the exe ──────────────────────────────────────────────
set "BOT_EXE="

:: Check dist subfolder first (build output location)
if exist "%SETUP_DIR%dist\morning_bot\morning_bot.exe" (
    set "BOT_EXE=%SETUP_DIR%dist\morning_bot\morning_bot.exe"
    set "BOT_DIR=%SETUP_DIR%dist\morning_bot"
    goto :found_exe
)

:: Check same folder (flat deployment)
if exist "%SETUP_DIR%morning_bot.exe" (
    set "BOT_EXE=%SETUP_DIR%morning_bot.exe"
    set "BOT_DIR=%SETUP_DIR%"
    goto :found_exe
)

echo ERROR: morning_bot.exe not found.
echo.
echo Expected at one of:
echo   %SETUP_DIR%dist\morning_bot\morning_bot.exe
echo   %SETUP_DIR%morning_bot.exe
echo.
echo If you haven't built the exe yet, run build_exe.bat first.
pause
exit /b 1

:found_exe

echo.
echo  ============================================
echo    Morning Momentum Bot - Setup
echo  ============================================
echo.
echo  EXE:  %BOT_EXE%
echo.

:: ── Ensure config.json exists next to exe ───────────────────────
if not exist "%BOT_DIR%\config.json" (
    if exist "%SETUP_DIR%config.json" (
        echo [*] Copying config.json to exe directory...
        copy /y "%SETUP_DIR%config.json" "%BOT_DIR%\config.json" >nul
    ) else (
        echo WARNING: config.json not found!
        echo          The bot will create a default one on first run.
    )
)

:: ── Create images cache folder ──────────────────────────────────
if not exist "%BOT_DIR%\images" mkdir "%BOT_DIR%\images"

:: ── Register Windows Scheduled Task ─────────────────────────────
echo [*] Registering Windows Scheduled Task...
echo     Task name: %TASK_NAME%

:: Delete old task if exists
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Create task to run at logon
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%BOT_EXE%\"" ^
    /sc onlogon ^
    /rl limited ^
    /f

if errorlevel 1 (
    echo.
    echo WARNING: Could not create scheduled task.
    echo          You can still start the bot manually with start_bot.bat
    echo          Or create a shortcut to the exe in your Startup folder:
    echo            %%APPDATA%%\Microsoft\Windows\Start Menu\Programs\Startup
) else (
    echo     Scheduled task registered: auto-starts at every logon
)

:: ── Start the bot now ───────────────────────────────────────────
echo.
echo [*] Starting the bot...
start "" "%BOT_EXE%"

echo.
echo  ============================================
echo    Setup Complete!
echo  ============================================
echo.
echo  The bot is now running in your system tray.
echo  Look for the sun icon (top/bottom right of taskbar).
echo.
echo  Right-click the tray icon for:
echo    - Check Now
echo    - Show Last Image
echo    - Quit
echo.
echo  It will auto-start every time you log in.
echo.
pause
