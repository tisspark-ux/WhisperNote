@echo off
echo ======================================
echo  WhisperNote Setup
echo ======================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Please install Python 3.10+ from https://python.org
    pause & exit /b 1
)

if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
) else (
    echo [1/4] Virtual environment already exists, skipping.
)

call .venv\Scripts\activate.bat

echo [2/4] Installing PyTorch (CUDA 12.1 for RTX A4000)...
pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121 -q
if errorlevel 1 (
    echo.
    echo [ERROR] PyTorch installation failed.
    echo.
    echo The company network may be blocking download.pytorch.org
    echo Please download the wheel files manually on a personal PC:
    echo.
    echo   1. Go to: https://download.pytorch.org/whl/cu121
    echo   2. Download: torch, torchvision, torchaudio for Python 3.10 / win_amd64
    echo   3. Copy the .whl files into this folder
    echo   4. Run: pip install torch*.whl torchvision*.whl torchaudio*.whl
    echo.
    pause & exit /b 1
)

echo [3/4] Installing packages...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Package installation failed.
    pause & exit /b 1
)

echo [4/4] Checking Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
    echo.
    echo [INFO] Ollama not found.
    echo Please install from https://ollama.com then run:
    echo   ollama pull exaone3.5:latest
) else (
    echo Downloading EXAONE 3.5 model (first time only)...
    ollama pull exaone3.5:latest
)

echo.
echo ======================================
echo  Setup complete! Run run.bat to start.
echo ======================================
pause
