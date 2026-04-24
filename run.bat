@echo off

rem Disable Quick Edit Mode immediately in THIS window (prevents freeze on click)
python                    -c "import ctypes;k=ctypes.windll.kernel32;h=k.GetStdHandle(-10);m=ctypes.c_ulong();k.GetConsoleMode(h,ctypes.byref(m));k.SetConsoleMode(h,(m.value&~0x40)|0x80)" >nul 2>&1
py                        -c "import ctypes;k=ctypes.windll.kernel32;h=k.GetStdHandle(-10);m=ctypes.c_ulong();k.GetConsoleMode(h,ctypes.byref(m));k.SetConsoleMode(h,(m.value&~0x40)|0x80)" >nul 2>&1
.venv\Scripts\python.exe  -c "import ctypes;k=ctypes.windll.kernel32;h=k.GetStdHandle(-10);m=ctypes.c_ulong();k.GetConsoleMode(h,ctypes.byref(m));k.SetConsoleMode(h,(m.value&~0x40)|0x80)" >nul 2>&1

rem Set QuickEdit=0 in registry for the WhisperNote console window BEFORE creating it.
rem Windows reads HKCU\Console\<title> at window creation time, so this must run first.
.venv\Scripts\python.exe -c "import winreg as r;k=r.CreateKey(r.HKEY_CURRENT_USER,'Console\\WhisperNote');r.SetValueEx(k,'QuickEdit',0,r.REG_DWORD,0);r.CloseKey(k)" >nul 2>&1

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    echo Starting Ollama...
    start /min "" ollama serve
    timeout /t 2 /nobreak >nul
)

echo Starting WhisperNote...
set PYTHONHTTPSVERIFY=0
set no_proxy=localhost,127.0.0.1,0.0.0.0
set NO_PROXY=localhost,127.0.0.1,0.0.0.0

rem /k keeps the window open after crash so the error is visible.
start "WhisperNote" cmd /k python app.py

rem Wait until port 7860 is actually listening (max 150s, checks every 2s).
rem torch/whisperX imports can take 60+ seconds on first run.
echo Waiting for server (may take 1-2 minutes on first run)...
set _t=0
:_wait
if %_t% GEQ 75 goto _open
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
