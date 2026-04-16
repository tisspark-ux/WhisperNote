# WhisperNote 실행 스크립트
# PowerShell 실행: run.bat 더블클릭

$Host.UI.RawUI.WindowTitle = "WhisperNote"

# 가상환경 활성화 (있으면)
$activateScript = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
}

# Ollama 실행 (이미 실행 중이면 무시)
$ollamaRunning = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if (-not $ollamaRunning) {
    Write-Host "Ollama 시작 중..." -ForegroundColor DarkGray
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# 앱 실행
Write-Host "WhisperNote 시작 중..." -ForegroundColor Cyan
python app.py
