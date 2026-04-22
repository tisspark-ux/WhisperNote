__version__ = "1.0.5"

CHANGELOG = """
v1.0.5 (2026-04-22)
  - [기능] 녹음 시간 실시간 표시 — 전체/파트별 경과 시간 (HH:MM:SS)
  - 일시정지 중 타이머 정지, 재개 시 이어서 증가 (주황색 표시)
  - /api/level 응답에 elapsed 정보 포함, 기존 JS polling으로 200ms 갱신
  - recorder.py: get_elapsed(), _fmt_time(), 타이밍 필드 추가
  - app.py: timer_display HTML 추가, _LEVEL_JS 타이머 DOM 업데이트


v1.0.4 (2026-04-22)
  - [기능] 볼륨 슬라이더 추가 — 마이크/시스템 오디오 게인 실시간 조정 (0.5x~4.0x)
  - 입력 모드에 따라 슬라이더 표시/숨김: 대면회의=마이크, 원격회의=시스템, 원격+원격회의=둘 다
  - 슬라이더 변경 즉시 recorder.mic_gain/system_gain 반영 → 레벨 미터도 실시간 반영
  - recorder.py: mic_gain/system_gain 필드, 콜백/WASAPI 스레드 모두 게인 적용


v1.0.3 (2026-04-22)
  - [기능] 입력 장치 드롭다운 문구 개편 — 상황별 4가지 선택지로 단순화
  - (PC) 🎙 대면회의 / (PC) 🎧 원격회의 / (원격) 🖥 대면회의 / (원격) 🎙+🎧 원격회의
  - [기능] (원격) 🎙+🎧 원격회의: RDP 마이크 + WASAPI 루프백 동시 녹음 및 믹싱 추가
  - [개선] (PC) 🎧 원격회의: WASAPI 실패 시 Stereo Mix 자동 폴백
  - recorder.py: start(mixed=True), _run_wasapi_mix(), _mix_audio_data 추가
  - app.py: _MIX_AUTO(-5) sentinel, 드롭다운 문구 변경, handle_start_recording/handle_mic_test 분기 추가


v1.0.2 (2026-04-22)
  - [기능] WASAPI 루프백 녹음 추가 — Teams/Zoom/브라우저 등 시스템 오디오 캡처
  - requirements.txt: soundcard 추가
  - recorder.py: _run_wasapi_loopback(), start/start_test에 wasapi_loopback 파라미터
  - app.py: _WASAPI_AUTO(-4) sentinel, "시스템 오디오 (WASAPI 루프백)" 드롭다운 옵션


v1.0.1 (2026-04-22)
  - [기능] RDP 원격 마이크 자동감지 지원 — "원격 마이크 자동감지" 드롭다운 옵션 추가
  - recorder.py: _RDP_KEYWORDS, is_rdp_device_name(), find_rdp_device() 추가
  - recorder.py: list_devices() 개선 — 호스트 API 이름, [원격] 태그, ch:0 경고 표시
  - app.py: _REMOTE_AUTO(-3) sentinel, handle_start_recording/handle_mic_test RDP 분기 추가


v1.0.0 (2026-04-22)
  - [기능] 전사 파일 다중 선택 병합 — 여러 파트 전사문을 이름순(시간순) 병합 후 교정/요약
  - app.py: handle_load_transcripts() 추가, 전사 파일 병합 UI 섹션 추가
  - app.py: merged_stem_state(gr.State) 추가 — 병합 파일명 기반으로 교정/요약 파일 저장
  - app.py: handle_correct/handle_summarize에 merged_stem 파라미터 추가
  - app.py: handle_transcribe/handle_pipeline 실행 시 merged_stem_state 초기화


v0.9.9 (2026-04-22)
  - [기능] 전사 교정 기능 추가 - LLM이 구어체/추임새 교정, 별도 파일 저장
  - [기능] 요약 시 원본/교정본 선택 라디오 추가
  - config.py: CORRECTION_PROMPT_TEMPLATE 추가
  - summarizer.py: correct_transcript() 메서드 추가
  - app.py: 교정 결과 UI, btn_correct, transcript_source_radio 추가


v0.9.8 (2026-04-22)
  - [기능] 자동 분할 녹음 추가 (기본 30분, 0=끄기)
  - 녹음 중 N분마다 _part01.wav, _part02.wav... 자동 저장
  - UI: 자동 분할 분 입력란 추가, gr.Timer로 청크 저장 알림 실시간 표시
  - config.py: RECORDING_CHUNK_MINUTES 추가


v0.9.7 (2026-04-22)
  - [개선] 전사 품질 향상: beam_size 5→10, VAD 필터 활성화, 한국어 초기 프롬프트 추가
  - [개선] temperature=0 (결정론적 출력), condition_on_previous_text=True (문맥 연속성)
  - config.py: WHISPER_BEAM_SIZE, WHISPER_VAD_FILTER, WHISPER_INITIAL_PROMPT 추가


v0.9.6 (2026-04-22)
  - [기능] 전사 결과 파일 경로 옆 "📂 폴더 열기" 버튼 추가
  - [기능] 요약 결과 파일 경로 옆 "📂 폴더 열기" 버튼 추가


v0.9.5 (2026-04-22)
  - [기능] 녹음 파일 경로 옆 "📂 폴더 열기" 버튼 추가
  - Windows: explorer로 해당 폴더 열기, 기타 OS: os.startfile fallback


v0.9.4 (2026-04-21)
  - [수정] 분류 설정 패널 라디오 항목 이름 표시 안 되는 버그 수정 (span CSS 제거)
  - [수정] "접기" 버튼 레이아웃 깨짐 수정 (position: absolute 고정)
  - [수정] 메인 화면 소분류 드롭다운 선택 불가 수정 (패널 닫힐 때 choices 재동기화)
  - app.py: sync_dropdowns_on_close 추가, btn_cat_close.click 연결 변경


v0.9.3 (2026-04-21)
  - [수정] 레벨 미터 깜빡임 완전 제거
  - Gradio SSE 갱신 방식 → JavaScript setInterval + /api/level 폴링으로 교체
  - DOM 직접 조작(textContent/style.color)으로 innerHTML 교체 없음

v0.9.2 (2026-04-21)
  - [수정] 레벨 미터 0.2초 갱신 시 레이아웃 깜빡임 현상 수정
  - gr.HTML elem_id + CSS height 고정으로 Gradio 갱신 중 높이 변화 방지
  - get_level_html: 항상 동일한 height:36px flex 컨테이너로 렌더링

v0.9.1 (2026-04-21)
  - [변경] 분류 파일 저장 경로 sessions/ → outputs/L1/L2/L3/ 로 변경
  - storage.py: SESSIONS_DIR 제거, OUTPUTS_DIR 기반으로 통일
  - config.py: SESSIONS_DIR 항목 제거

v0.9.0 (2026-04-21)
  - [기능] 3단계 분류 선택 (대분류/중분류/소분류) — Studio 탭 녹음 위
  - [기능] 분류 설정 패널 (Miller Column) — 추가/수정/삭제 인라인 CRUD
  - [기능] 분류 선택 시 sessions/L1/L2/L3/ 에 WAV+전사+요약 통합 저장
  - [기능] 저장 경로 미리보기 표시
  - app.py: cat_mod/storage 연동, handle 함수 4개에 output_dir 적용

v0.8.1 (2026-04-20)
  - [리팩토링] categories.py 신규: 카테고리 트리 CRUD + categories.json 영속화
  - [리팩토링] storage.py 신규: 카테고리 → 파일 경로 변환 (sessions/ 기반)
  - [리팩토링] config.py: SESSIONS_DIR, CATEGORIES_FILE 경로 추가
  - [리팩토링] recorder.start(output_dir=None): 카테고리 폴더 지원 준비
  - [리팩토링] transcriber.transcribe(output_dir=None): 카테고리 폴더 지원 준비
  - [리팩토링] summarizer.summarize(output_dir=None): 카테고리 폴더 지원 준비
  - 기존 동작 완전 보존 (output_dir=None 시 recordings/, outputs/ 사용)

v0.8.0 (2026-04-20)
  - [기능] 루프백 장치 감지 키워드 확장 (한글 장치명, Virtual Audio Cable, Voicemeeter 등)
  - [기능] UI 드롭다운에 "루프백 자동감지" 선택지 추가
  - [기능] 드롭다운 및 설정 탭 장치 목록에 [루프백] 태그 표시
  - [수정] 루프백 장치 수동 선택 시 source_label "마이크:" 오표시 버그 수정
  - recorder.py: _LOOPBACK_KEYWORDS + is_loopback_device_name() + find_loopback_device() 추가
  - app.py: _LOOPBACK_AUTO(-2) sentinel, get_input_device_choices/handle_start_recording/handle_mic_test 개선

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
