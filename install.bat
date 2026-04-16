@echo off
echo ======================================
echo  WhisperNote Setup
echo ======================================
echo.

:: Python check
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause & exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo   %%i

:: Python version warning (3.13+ may have compatibility issues)
for /f "tokens=2" %%v in ('python --version') do set PY_VER=%%v
for /f "tokens=2 delims=." %%a in ("%PY_VER%") do set PY_MIN=%%a
if %PY_MIN% GTR 12 (
    echo   [WARN] Python %PY_VER% is very new. Recommended: Python 3.11 or 3.12
    echo   Some packages may fail. Continuing in 5 seconds...
    timeout /t 5 /nobreak >nul
)

:: Virtual environment
if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
) else (
    echo [1/4] Virtual environment exists, skipping.
)

set PIP=.venv\Scripts\pip.exe
set PYTHON=.venv\Scripts\python.exe

:: Upgrade pip first to ensure binary wheel support
%PYTHON% -m pip install --upgrade pip -q

:: PyTorch (CUDA 13.0 / RTX A4000)
echo [2/4] Installing PyTorch...
%PYTHON% -c "import torch" >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%v in ('%PYTHON% -c "import torch; print(torch.__version__)"') do echo   PyTorch %%v already installed, skipping.
    goto torch_done
)
%PIP% install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130 -q
if errorlevel 1 (
    echo [ERROR] PyTorch installation failed.
    pause & exit /b 1
)
echo   PyTorch installed.
:torch_done

:: Other packages
echo [3/4] Installing packages...
%PIP% install webrtcvad-wheels -q
%PIP% install resemblyzer --no-deps -q
%PIP% install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Package installation failed.
    pause & exit /b 1
)
echo   Packages installed.

:: Ollama
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
echo ======================================
pause
