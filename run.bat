@echo off
chcp 65001 > nul

:: 가상환경 활성화 (있으면)
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Ollama 백그라운드 실행 (이미 실행 중이면 무시)
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" > nul
if errorlevel 1 (
    echo Ollama 시작 중...
    start /min "" ollama serve
    timeout /t 2 > nul
)

:: 앱 실행
python app.py
