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
set no_proxy=localhost,127.0.0.1,0.0.0.0
set NO_PROXY=localhost,127.0.0.1,0.0.0.0

rem Start Gradio server in a separate window so logs stay visible.
start "WhisperNote" python app.py

rem Wait for Gradio to start, then open browser.
rem Proxy bypass is handled by app.py via winreg at startup.
timeout /t 6 /nobreak >nul
start http://127.0.0.1:7860

echo.
echo Access: http://127.0.0.1:7860
echo Close the WhisperNote window to stop the server.
