@echo off
:: ================================================================
::  Reorganize GitHub Repo: sureshgce/morning-motivation
::
::  This script:
::    1. Clones the repo
::    2. Creates an images/ folder
::    3. Moves all image files into images/
::    4. Commits and pushes
::
::  Run this ONCE from any machine that has Git installed.
::  After running, the repo structure will be:
::    morning-motivation/
::    └── images/
::        ├── 10-03-2026.png
::        ├── 11-03-2026.png
::        └── ...
:: ================================================================

setlocal EnableDelayedExpansion

set "REPO_URL=https://github.com/sureshgce/morning-motivation.git"
set "CLONE_DIR=%TEMP%\morning-motivation-reorg"
set "IMG_FOLDER=images"

echo.
echo  ============================================
echo    Reorganize: morning-motivation repo
echo  ============================================
echo.

:: ── Check git ───────────────────────────────────────────────────
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not installed or not on PATH.
    echo        Install Git from https://git-scm.com
    pause
    exit /b 1
)

:: ── Clone ───────────────────────────────────────────────────────
echo [1/4] Cloning repository...
if exist "%CLONE_DIR%" rd /s /q "%CLONE_DIR%"
git clone "%REPO_URL%" "%CLONE_DIR%"
if errorlevel 1 (
    echo ERROR: Clone failed. Check your network and repo URL.
    pause
    exit /b 1
)

cd /d "%CLONE_DIR%"
echo        Cloned to: %CLONE_DIR%

:: ── Create images/ folder ───────────────────────────────────────
echo.
echo [2/4] Creating images/ folder...
if not exist "%IMG_FOLDER%" mkdir "%IMG_FOLDER%"

:: ── Move all image files to images/ ─────────────────────────────
echo.
echo [3/4] Moving image files into images/ ...
set "MOVED=0"

for %%E in (jpg jpeg png gif bmp webp tif tiff svg ico) do (
    for %%F in (*.%%E) do (
        if exist "%%F" (
            echo        Moving: %%F
            move /y "%%F" "%IMG_FOLDER%\" >nul
            set /a MOVED+=1
        )
    )
)

if %MOVED%==0 (
    echo        No image files found at repo root.
    echo        Images may already be in the images/ folder.
) else (
    echo        Moved %MOVED% image(s) into images/
)

:: ── Commit and push ─────────────────────────────────────────────
echo.
echo [4/4] Committing and pushing...
git add -A
git commit -m "Reorganize: move all images into images/ folder"
git push

if errorlevel 1 (
    echo.
    echo ERROR: Push failed.
    echo        You may need to authenticate or have write access.
    echo        Try: git -C "%CLONE_DIR%" push
    pause
    exit /b 1
)

echo.
echo  ============================================
echo    Done! Repo reorganized successfully.
echo  ============================================
echo.
echo  New structure:
echo    morning-motivation/
echo    └── images/
echo        ├── 10-03-2026.png
echo        ├── 11-03-2026.png
echo        └── ...
echo.
echo  The bot is already configured to read from images/
echo.

:: ── Cleanup ─────────────────────────────────────────────────────
cd /d "%~dp0"
rd /s /q "%CLONE_DIR%" >nul 2>&1

pause
