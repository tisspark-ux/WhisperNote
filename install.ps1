# WhisperNote 설치 스크립트
# PowerShell 실행: install.bat 더블클릭

$Host.UI.RawUI.WindowTitle = "WhisperNote 설치"

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  WhisperNote 설치" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Python 확인
Write-Host "[확인] Python 버전 확인 중..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[오류] Python 이 설치되어 있지 않습니다." -ForegroundColor Red
    Write-Host "  https://python.org 에서 Python 3.10 이상을 설치하세요."
    Read-Host "엔터를 눌러 종료"
    exit 1
}

# 가상환경 생성
if (-not (Test-Path ".venv")) {
    Write-Host ""
    Write-Host "[1/4] 가상환경 생성 중..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "  완료" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[1/4] 가상환경 이미 존재, 건너뜀" -ForegroundColor DarkGray
}

# 가상환경 활성화
$activateScript = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
& $activateScript

# PyTorch CUDA 설치
Write-Host ""
Write-Host "[2/4] PyTorch (CUDA 12.1) 설치 중..." -ForegroundColor Yellow
Write-Host "  RTX A4000 GPU 최적화 버전입니다. 시간이 걸릴 수 있습니다."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 -q
Write-Host "  완료" -ForegroundColor Green

# 패키지 설치
Write-Host ""
Write-Host "[3/4] 패키지 설치 중..." -ForegroundColor Yellow
pip install -r requirements.txt -q
Write-Host "  완료" -ForegroundColor Green

# Ollama 확인 및 모델 다운로드
Write-Host ""
Write-Host "[4/4] Ollama 모델 확인 중..." -ForegroundColor Yellow
$ollamaExists = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaExists) {
    Write-Host ""
    Write-Host "  [안내] Ollama 가 설치되어 있지 않습니다." -ForegroundColor DarkYellow
    Write-Host "  https://ollama.com 에서 설치 후 아래 명령을 실행하세요:"
    Write-Host "    ollama pull exaone3.5:latest" -ForegroundColor Cyan
} else {
    Write-Host "  EXAONE 3.5 모델 다운로드 중... (최초 1회만 실행)"
    ollama pull exaone3.5:latest
    Write-Host "  완료" -ForegroundColor Green
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  설치 완료! run.bat 으로 실행하세요." -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "엔터를 눌러 종료"
