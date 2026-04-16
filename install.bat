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
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 -q

echo [3/4] Installing packages...
pip install -r requirements.txt -q

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
