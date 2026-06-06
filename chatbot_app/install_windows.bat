@echo off
title AI Chatbot Setup
cls
echo.
echo   =====================================
echo   AI Chatbot - Windows Setup
echo   =====================================
echo.

:: ── Step 1: Python ──
python --version >nul 2>&1
if errorlevel 1 (
    echo   Python not found.
    echo   Opening python.org — install it, then re-run this file.
    echo   IMPORTANT: Check "Add Python to PATH" during install!
    pause
    start https://www.python.org/downloads/
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo   ✓ %%i

:: ── Step 2: Ollama ──
ollama --version >nul 2>&1
if errorlevel 1 (
    echo   Ollama not found.
    echo   Opening ollama.com — install it, then re-run this file.
    pause
    start https://ollama.com/download
    exit /b 1
)
echo   ✓ Ollama found

:: ── Step 3: Start Ollama ──
echo   Starting Ollama...
taskkill /f /im "ollama.exe" >nul 2>&1
timeout /t 1 /nobreak >nul
start /b ollama serve
timeout /t 4 /nobreak >nul
echo   ✓ Ollama running

:: ── Step 4: Pull model ──
echo   Downloading AI model (qwen2.5:7b, ~4GB - only once)...
ollama pull qwen2.5:7b
echo   ✓ AI model ready

:: ── Step 5: Python packages ──
echo   Installing Python packages...
python -m pip install -q customtkinter ollama
echo   ✓ Packages installed

echo.
echo   ✓ All done! Launching chatbot...
echo.

:: ── Step 6: Launch ──
python "%~dp0chatbot_app.py"
pause
