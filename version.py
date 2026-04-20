__version__ = "0.5.0"

CHANGELOG = """
v0.5.0 (2026-04-20)
  - Gradio url_ok 패치 안전성 강화 (try/except + hasattr 가드)
  - requirements.txt에 scipy 명시적 추가
  - 설정 탭 문서 정정: large-v3-turbo / ~1.6 GB

v0.4.0 (2026-04-19)
  - Whisper 모델 large-v3 → large-v3-turbo (속도/정확도 향상)
  - 회사 프록시 localhost 차단 우회: no_proxy 환경변수 + requests 패치
  - Gradio url_ok 패치로 ValueError 해결
  - show_api=False로 Gradio TypeError 우회

v0.3.0 (2026-04-18)
  - PyAV로 ffmpeg 바이너리 의존성 제거 (GitHub 차단 환경 대응)
  - HuggingFace 모델 캐시 → 로컬 models/ 폴더 (HF_HOME 재지정)
  - whisperx.load_audio 패치: soundfile + PyAV fallback
  - 회사 프록시 SSL 인증서 우회 (requests verify=False)

v0.2.0 (2026-04-17)
  - resemblyzer --no-deps 설치로 webrtcvad C++ 빌드 오류 해결
  - install.bat: py 런처로 Python 버전 자동 선택 (3.12 > 3.11 > 3.13)

v0.1.0 (2026-04-16)
  - 최초 구현: 녹음 → WhisperX 전사 → 화자 분리 → Ollama 요약
  - resemblyzer + SpectralClustering 기반 오프라인 화자 분리
  - Gradio 다크 테마 UI (Studio / 설정 탭)
"""
