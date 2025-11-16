@echo off
REM Startup script for Alpha Arena Mini (Windows)
REM Launches web server and bot in the correct order

echo ====================================================================
echo ALPHA ARENA MINI - STARTUP
echo ====================================================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv venv
    echo Then run: venv\Scripts\activate
    echo Then run: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Run the Python startup script
venv\Scripts\python.exe start_bot.py

pause
