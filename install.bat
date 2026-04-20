@echo off
echo ======================================
echo  WhisperNote Setup
echo ======================================
echo.

rem All pip output is saved to install_log.txt for review.
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

rem Upgrade pip
%PYTHON% -m pip install --upgrade pip >> %LOG% 2>&1

rem PyTorch (CUDA 13.0 / RTX A4000)
echo [2/4] Installing PyTorch...
%PYTHON% -c "import torch" >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%v in ('%PYTHON% -c "import torch; print(torch.__version__)"') do echo   PyTorch %%v already installed, skipping.
    goto torch_done
)
echo   Downloading PyTorch (CUDA 13.0) — this may take a while...
%PIP% install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130 >> %LOG% 2>&1
if errorlevel 1 (
    echo [ERROR] PyTorch installation failed. Details:
    type %LOG%
    pause & exit /b 1
)
echo   PyTorch installed.
:torch_done

rem Other packages
echo [3/4] Installing packages...
echo --- webrtcvad-wheels --- >> %LOG%
%PIP% install webrtcvad-wheels >> %LOG% 2>&1
echo --- resemblyzer (no-deps) --- >> %LOG%
%PIP% install resemblyzer --no-deps >> %LOG% 2>&1
echo --- requirements.txt --- >> %LOG%
%PIP% install -r requirements.txt >> %LOG% 2>&1
if errorlevel 1 (
    echo [ERROR] Package installation failed. Details:
    echo.
    type %LOG%
    echo.
    pause & exit /b 1
)
echo   Packages installed. (full log: %LOG%)

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
echo  Setup complete! Run run.bat to start.
echo  Install log saved to: %LOG%
echo ======================================
pause
