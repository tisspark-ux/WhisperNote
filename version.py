__version__ = "0.7.0"

CHANGELOG = """
v0.7.0 (2026-04-20)
  - [기능] 녹음 중 일시정지/재개 (⏸ / ▶ 버튼)
  - [기능] 녹음 시작 전 마이크 테스트 (레벨 미터로 입력 확인)
  - [변경] 녹음 완료 후 자동 전사/요약 비활성화 (수동 실행으로 변경)
  - recorder.py: pause/resume/start_test/stop_test 메서드 추가
  - recorder.py: _open_input_stream 공통 장치 열기 로직 분리
  - app.py: 버튼 상태 6개 반환으로 확장, 레벨 미터 테스트/일시정지 상태 표시

v0.6.9 (2026-04-20)
  - CLAUDE.md: 수정 후 영향도 체크 및 커밋 전 코드 점검 규칙 추가
  - app.py: demo.load에서 gr.Dropdown() -> gr.update() 수정 (Gradio 4.x 호환)
  - app.py: handle_start_recording device_idx None 처리 추가

v0.6.8 (2026-04-20)
  - UI: 녹음 버튼 위에 입력 장치 드롭다운 추가 (자동 감지 / 개별 선택)
  - UI: 녹음 중 오디오 레벨 미터 표시 (0.2초 갱신, 80% 이상 빨간색)
  - recorder.py: start(device_override) — UI 선택 장치 직접 전달
  - recorder.py: get_level() — 최근 버퍼 RMS 0~100 반환

v0.6.7 (2026-04-20)
  - transcriber.py: faster_whisper.WhisperModel 직접 사용 (whisperx.load_model 대체)
    whisperx.load_model이 pyannote/segmentation VAD 필요 -> 인증 실패 문제 우회
  - transcriber.py: vad_filter=False, 정렬 단계에서만 whisperx 사용 (선택적)
  - recorder.py: 녹음 시작 상태에 실제 장치명 표시
  - CLAUDE.md: 계획 파일 한국어 작성 규칙 추가

v0.6.6 (2026-04-20)
  - app.py: auto pipeline (transcribe + summarize) after recording stops via .then()

v0.6.5 (2026-04-20)
  - recorder.py: fallback to first available input device when default is -1
  - recorder.py: helpful Korean error message with device list when no mic found

v0.6.4 (2026-04-20)
  - app.py: unhandled exceptions logged to whispernote_error.log (utf-8, timestamp)
  - sys.excepthook: errors shown in console window AND saved to file
  - .gitignore: whispernote_error.log excluded

v0.6.3 (2026-04-20)
  - app.py: Korean progress prints before heavy imports (flush=True) - no more black window
  - run.bat: netstat timeout 60s -> 150s (torch/whisperx can take 60+ sec)
  - CLAUDE.md: Korean console message rule added

v0.6.2 (2026-04-20)
  - install.bat: pip -q shows download progress bar only (hides verbose collecting/building text)
  - install.bat: stderr-only log (install_log.txt) - errors captured, normal output clean
  - install.bat: per-step error check for [3a/3b/3c] with log dump on failure

v0.6.1 (2026-04-20)
  - install.bat: remove final pause on success, auto-launch run.bat after install
  - run.bat: confirmed no pause (no change needed)
  - CLAUDE.md: add Korean-only response rule

v0.6.0 (2026-04-20)
  - gradio_client.utils 3종 함수 일괄 패치: _json_schema_to_python_type,
    get_type, get_desc — boolean schema 처리 누락으로 인한 TypeError 완전 해결
  - bat 파일 ASCII-only 정책: 한글 주석 제거, :: → rem 전환
  - 브라우저 프록시 우회를 app.py winreg로 이전 (run.bat 단순화)
  - run.bat: netstat 폴링으로 포트 열릴 때만 브라우저 실행
  - cmd /k로 WhisperNote 창 크래시 후에도 유지 (에러 확인 가능)

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
