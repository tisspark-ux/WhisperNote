@echo off
echo ======================================
echo  WhisperNote - Whisper Model Download
echo ======================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found.
    echo Run install.bat first to set up the virtual environment.
    pause & exit /b 1
)

set PYTHON=.venv\Scripts\python.exe
set LOG=%~dp0whisper_install.log

echo Log file: %LOG%
echo.

%PYTHON% %~dp0download_whisper.py --log %LOG%

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
pause
