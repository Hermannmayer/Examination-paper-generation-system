@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run: python -m venv .venv
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
echo.
echo Virtual environment activated. Type "deactivate" to exit.
echo.
cmd
