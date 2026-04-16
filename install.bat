@echo off
chcp 65001 > nul
echo ======================================
echo  WhisperNote 설치
echo ======================================
echo.

:: Python 확인
python --version > nul 2>&1
if errorlevel 1 (
    echo [오류] Python 이 설치되어 있지 않습니다.
    echo  https://python.org 에서 Python 3.10 이상을 설치하세요.
    pause & exit /b 1
)

:: 가상환경 생성
if not exist ".venv" (
    echo [1/4] 가상환경 생성 중...
    python -m venv .venv
) else (
    echo [1/4] 가상환경 이미 존재
)

:: 가상환경 활성화
call .venv\Scripts\activate.bat

:: PyTorch CUDA 설치 (RTX A4000 - CUDA 12.1)
echo [2/4] PyTorch ^(CUDA 12.1^) 설치 중...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 -q

:: 나머지 패키지 설치
echo [3/4] 패키지 설치 중...
pip install -r requirements.txt -q

:: Ollama 확인
echo [4/4] Ollama 모델 확인 중...
where ollama > nul 2>&1
if errorlevel 1 (
    echo.
    echo [안내] Ollama 가 설치되어 있지 않습니다.
    echo  https://ollama.com 에서 설치 후 아래 명령 실행:
    echo    ollama pull exaone3.5:latest
) else (
    echo  EXAONE 3.5 모델 다운로드 중... ^(처음에만 시간이 걸립니다^)
    ollama pull exaone3.5:latest
)

echo.
echo ======================================
echo  설치 완료! run.bat 으로 실행하세요.
echo ======================================
pause
