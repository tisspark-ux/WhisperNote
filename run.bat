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

for /f "tokens=*" %%v in ('python -c "from version import __version__; print(__version__)"') do set WN_VER=%%v
echo Starting WhisperNote v%WN_VER%...
set PYTHONHTTPSVERIFY=0
set no_proxy=localhost,127.0.0.1,0.0.0.0
set NO_PROXY=localhost,127.0.0.1,0.0.0.0

:: Python/Gradio 를 별도 창에서 실행 (오류 로그 확인 가능)
start "WhisperNote v%WN_VER%" python app.py

:: Gradio 서버 준비 대기
echo Waiting for server to start...
timeout /t 6 /nobreak >nul

:: 회사 프록시를 우회하여 Edge 실행
:: <-loopback> = Chromium 계열에서 loopback 주소 프록시 제외 플래그
echo Opening browser...
start "" "msedge" --proxy-bypass-list="<-loopback>;localhost;127.0.0.1" http://127.0.0.1:7860

echo.
echo ======================================
echo  WhisperNote v%WN_VER% is running
echo  Access: http://127.0.0.1:7860
echo.
echo  If browser shows proxy error, add
echo  127.0.0.1 to Windows proxy bypass:
echo  Settings ^> Network ^> Proxy ^> bypass
echo ======================================
