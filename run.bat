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

for /f "tokens=*" %%v in ('python -c "from version import __version__; print(__version__)"') do echo Starting WhisperNote v%%v...
set PYTHONHTTPSVERIFY=0
set no_proxy=localhost,127.0.0.1,0.0.0.0
set NO_PROXY=localhost,127.0.0.1,0.0.0.0
python app.py
if errorlevel 1 (
    echo.
    echo [ERROR] App failed to start. Check the error above.
    echo If packages are missing, run install.bat first.
    pause
)
