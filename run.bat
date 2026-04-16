@echo off
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    echo Starting Ollama...
    start /min "" ollama serve
    timeout /t 2 >nul
)

echo Starting WhisperNote...
set PYTHONHTTPSVERIFY=0
python app.py
if errorlevel 1 (
    echo.
    echo [ERROR] App failed to start. Check the error above.
    echo If packages are missing, run install.bat first.
    pause
)
