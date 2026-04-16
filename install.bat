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

:: Virtual environment
if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
) else (
    echo [1/4] Virtual environment exists, skipping.
)

:: Use explicit venv pip/python paths
set PIP=.venv\Scripts\pip.exe
set PYTHON=.venv\Scripts\python.exe

:: PyTorch — skip if already installed in venv
echo [2/4] Installing PyTorch...
%PYTHON% -c "import torch; print('  PyTorch', torch.__version__, 'already installed, skipping.')" 2>nul
if not errorlevel 1 goto torch_done

set TORCH_IDX=cpu
set CUDA_MAJ=0
set CUDA_MIN=0

nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo   No NVIDIA GPU detected. Installing CPU version.
) else (
    nvidia-smi > "%TEMP%\wn_nvsmi.txt" 2>&1
    for /f "tokens=9" %%v in ('findstr "CUDA Version" "%TEMP%\wn_nvsmi.txt"') do set CUDA_VER=%%v
    del "%TEMP%\wn_nvsmi.txt" >nul 2>&1

    if not defined CUDA_VER set CUDA_VER=12.1
    for /f "tokens=1 delims=." %%a in ("%CUDA_VER%") do set CUDA_MAJ=%%a
    for /f "tokens=2 delims=." %%a in ("%CUDA_VER%") do set CUDA_MIN=%%a
    if not defined CUDA_MIN set CUDA_MIN=0

    set TORCH_IDX=cu121
    if "%CUDA_MAJ%"=="11" set TORCH_IDX=cu118
    if "%CUDA_MAJ%"=="12" (
        if %CUDA_MIN% GEQ 4 set TORCH_IDX=cu124
    )
    if "%CUDA_MAJ%"=="13" set TORCH_IDX=cu130
    echo   CUDA %CUDA_VER% detected. Using PyTorch index: %TORCH_IDX%
)

if "%TORCH_IDX%"=="cpu" (
    %PIP% install torch torchvision torchaudio -q
) else (
    %PIP% install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/%TORCH_IDX% -q
)
if errorlevel 1 (
    echo [WARN] torchaudio not available for %TORCH_IDX%, trying without...
    %PIP% install torch torchvision --extra-index-url https://download.pytorch.org/whl/%TORCH_IDX% -q
    %PIP% install torchaudio -q
)
if errorlevel 1 (
    echo [ERROR] PyTorch installation failed. Supported Python: 3.9 - 3.12
    pause & exit /b 1
)
echo   PyTorch installed.

:torch_done

:: Other packages
echo [3/4] Installing packages...
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
