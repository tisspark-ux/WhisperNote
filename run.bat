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

rem Add 127.0.0.1 to Windows proxy bypass so the browser can reach the local server.
rem Uses PowerShell to safely read-then-append without overwriting existing entries.
powershell -NoProfile -Command "$k='HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'; $v=(Get-ItemProperty $k -EA 0).ProxyOverride; if($v -notlike '*127.0.0.1*'){$n=if($v){$v+';127.0.0.1;localhost'}else{'127.0.0.1;localhost'}; Set-ItemProperty $k ProxyOverride $n}" 2>nul

rem Start Gradio server in a separate window so its logs stay visible.
start "WhisperNote v%WN_VER%" python app.py

echo Waiting for server to start...
timeout /t 6 /nobreak >nul

rem Open default browser. Proxy bypass was already applied above.
echo Opening browser...
start http://127.0.0.1:7860

echo.
echo ======================================
echo  WhisperNote v%WN_VER% is running
echo  URL: http://127.0.0.1:7860
echo.
echo  If browser still shows an error,
echo  close Edge completely and reopen.
echo ======================================
