@echo off
echo ======================================
echo  WhisperNote Setup
echo ======================================
echo.

set LOG=install_log.txt
echo WhisperNote install log > %LOG%
date /t >> %LOG%
echo. >> %LOG%

rem Python version selection (prefer 3.12 > 3.11 > 3.13 > system default)
set PYTHON_CMD=python
py -3.13 --version >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py -3.13
py -3.11 --version >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py -3.11
py -3.12 --version >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py -3.12

%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause & exit /b 1
)
for /f "tokens=*" %%i in ('%PYTHON_CMD% --version') do echo   Using %%i

rem Virtual environment
if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
) else (
    echo [1/4] Virtual environment exists, skipping.
)

set PIP=.venv\Scripts\pip.exe
set PYTHON=.venv\Scripts\python.exe

rem Upgrade pip - silent (instant, no progress needed)
%PYTHON% -m pip install --upgrade pip -q >> %LOG% 2>&1

rem PyTorch (CUDA 13.0 / RTX A4000)
echo [2/4] Installing PyTorch...
%PYTHON% -c "import torch" >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%v in ('%PYTHON% -c "import torch; print(torch.__version__)"') do echo   PyTorch %%v already installed, skipping.
    goto torch_done
)
echo   Downloading PyTorch (CUDA 13.0) - may take several minutes...
%PIP% install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130 2>> %LOG%
if errorlevel 1 (
    echo [ERROR] PyTorch installation failed. Error details:
    type %LOG%
    pause & exit /b 1
)
echo   PyTorch installed.
:torch_done

rem Other packages
echo [3/4] Installing packages...
echo   [3a] webrtcvad-wheels...
%PIP% install webrtcvad-wheels -q 2>> %LOG%
if errorlevel 1 (
    echo [ERROR] webrtcvad-wheels failed. Error details:
    type %LOG%
    pause & exit /b 1
)
echo   [3b] resemblyzer...
%PIP% install resemblyzer --no-deps -q 2>> %LOG%
if errorlevel 1 (
    echo [ERROR] resemblyzer failed. Error details:
    type %LOG%
    pause & exit /b 1
)
echo   [3c] requirements.txt (may take a few minutes)...
%PIP% install -r requirements.txt 2>> %LOG%
if errorlevel 1 (
    echo [ERROR] requirements.txt failed. Error details:
    type %LOG%
    pause & exit /b 1
)
echo   Packages installed.

rem Ollama
echo [4/4] Checking Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
    echo   [INFO] Ollama not found. Install from https://ollama.com
    echo   Then run: ollama pull exaone3.5:latest
) else (
    echo   Downloading EXAONE 3.5 model (first time only)...
    ollama pull exaone3.5:latest
)

echo.
echo ======================================
echo  Setup complete! Starting WhisperNote...
echo ======================================
call run.bat
