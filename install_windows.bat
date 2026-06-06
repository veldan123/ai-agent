@echo off
echo.
echo ================================================
echo    Client Finder Agent -- Installer (Windows)
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed.
    echo Download it from https://python.org/downloads
    echo Make sure to tick "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [OK] Python found

:: Create folder
mkdir "%USERPROFILE%\Documents\contact_finder" 2>nul
cd /d "%USERPROFILE%\Documents\contact_finder"

:: Download agent files
echo.
echo Downloading agent files...
curl -fsSL https://raw.githubusercontent.com/veldan123/ai-agent/main/agent.py -o agent.py
curl -fsSL https://raw.githubusercontent.com/veldan123/ai-agent/main/requirements.txt -o requirements.txt

:: Install dependencies
echo.
echo Installing dependencies...
python -m pip install -r requirements.txt -q

echo.
echo ================================================
echo    Installation complete!
echo ================================================
echo.
echo NEXT STEP -- Install Ollama (the free AI):
echo   1. Go to https://ollama.com/download
echo   2. Download and install the Windows app
echo   3. Open Command Prompt and run:
echo.
echo      ollama pull qwen2.5:7b
echo.
echo Then start the agent:
echo.
echo      python "%USERPROFILE%\Documents\contact_finder\agent.py"
echo.
pause
