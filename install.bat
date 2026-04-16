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
call .venv\Scripts\activate.bat

:: Detect CUDA version and install PyTorch
echo [2/4] Installing PyTorch...
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo   No NVIDIA GPU detected. Installing CPU version.
    pip install torch torchvision torchaudio -q
) else (
    :: Parse CUDA version from nvidia-smi
    for /f "tokens=9" %%v in ('nvidia-smi ^| findstr "CUDA Version"') do set CUDA_VER=%%v
    for /f "tokens=1 delims=." %%a in ("%CUDA_VER%") do set CUDA_MAJ=%%a
    for /f "tokens=2 delims=." %%a in ("%CUDA_VER%") do set CUDA_MIN=%%a

    :: Map CUDA version to PyTorch index
    set TORCH_IDX=cu121
    if "%CUDA_MAJ%"=="11" set TORCH_IDX=cu118
    if "%CUDA_MAJ%"=="12" if %CUDA_MIN% GEQ 4 set TORCH_IDX=cu124

    echo   CUDA %CUDA_VER% detected. Using PyTorch %TORCH_IDX%.
    pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/%TORCH_IDX% -q
    if errorlevel 1 (
        echo [ERROR] PyTorch installation failed.
        echo   Check your Python version: python --version
        echo   Supported: Python 3.9 - 3.12
        pause & exit /b 1
    )
)

:: Other packages
echo [3/4] Installing packages...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Package installation failed.
    pause & exit /b 1
)

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
