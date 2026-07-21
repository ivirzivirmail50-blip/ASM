@echo off
REM ============================================================
REM  Absolute Story Manager — Windows launcher
REM  Checks for venv, installs requirements, starts Flask app
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set HOST=0.0.0.0
set PORT=3000

echo.
echo ============================================
echo   Absolute Story Manager v5.0 - Launcher
echo ============================================
echo.

REM --- Check Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo Install Python 3.11+ from https://python.org and re-run.
    pause
    exit /b 1
)

REM --- Check / create venv ---
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment found.
)

REM --- Activate venv ---
call .venv\Scripts\activate.bat

REM --- Install / update requirements ---
echo [INFO] Checking requirements...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)
echo [OK] Requirements installed.

REM --- Initialize DB if needed ---
if not exist "data\asm.db" (
    echo [INFO] Initializing database...
    set PYTHONPATH=.
    python scripts\init_db.py
    if errorlevel 1 (
        echo [WARN] DB init failed - the app will try again on first run.
    ) else (
        echo [OK] Database initialized.
    )
)

REM --- Set env vars ---
set FLASK_APP=app.py
set FLASK_ENV=development
set PYTHONPATH=.

echo.
echo ============================================
echo   Starting Absolute Story Manager...
echo   Browser will open at http://%HOST%:%PORT%/
echo   Press Ctrl+C to stop.
echo ============================================
echo.

REM --- Start app (browser opens automatically via app.py) ---
python app.py
pause
