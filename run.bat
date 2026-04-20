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

rem Wait until port 7860 is actually listening (max 60s, checks every 2s).
rem torch/whisperX imports can take 30+ seconds on first run.
echo Waiting for server (may take 30+ seconds on first run)...
set _t=0
:_wait
if %_t% GEQ 30 goto _open
timeout /t 2 /nobreak >nul
set /a _t+=1
netstat -an 2>nul | findstr ":7860" | findstr "LISTENING" >nul
if errorlevel 1 goto _wait
:_open
echo Server is ready. Opening browser...
start http://127.0.0.1:7860

echo.
echo Access: http://127.0.0.1:7860
echo Check the WhisperNote window for errors if the page fails to load.
