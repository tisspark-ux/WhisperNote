@echo off
echo ======================================
echo  WhisperNote - Whisper Model Download
echo ======================================
echo.

rem Disable Quick Edit Mode immediately - prevents window freeze on mouse click
python                   -c "import ctypes;k=ctypes.windll.kernel32;h=k.GetStdHandle(-10);m=ctypes.c_ulong();k.GetConsoleMode(h,ctypes.byref(m));k.SetConsoleMode(h,(m.value&~0x40)|0x80)" >nul 2>&1
py                       -c "import ctypes;k=ctypes.windll.kernel32;h=k.GetStdHandle(-10);m=ctypes.c_ulong();k.GetConsoleMode(h,ctypes.byref(m));k.SetConsoleMode(h,(m.value&~0x40)|0x80)" >nul 2>&1
.venv\Scripts\python.exe -c "import ctypes;k=ctypes.windll.kernel32;h=k.GetStdHandle(-10);m=ctypes.c_ulong();k.GetConsoleMode(h,ctypes.byref(m));k.SetConsoleMode(h,(m.value&~0x40)|0x80)" >nul 2>&1

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found.
    echo Run install.bat first to set up the virtual environment.
    pause & exit /b 1
)

set PYTHON=.venv\Scripts\python.exe
set LOG=%~dp0whisper_install.log

echo Log file: %LOG%
echo.

%PYTHON% %~dp0core\download_whisper.py --log %LOG%

if errorlevel 1 (
    echo.
    echo ======================================
    echo  DOWNLOAD FAILED
    echo ======================================
    echo.
    echo --- whisper_install.log ---
    type %LOG%
    echo ---------------------------
    echo.
    echo Share whisper_install.log with the developer for diagnosis.
    echo File location: %LOG%
    echo.
    pause
    exit /b 1
)

echo.
echo Log saved to: %LOG%
echo.
timeout /t 5 /nobreak >nul
