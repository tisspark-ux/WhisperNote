__version__ = "1.0.44"

CHANGELOG = """
v1.0.44 (2026-04-25)
  - [리팩토링] app.py 정리 완료 (2011줄 → 680줄): 모든 핸들러/CSS/워커 모듈 분리 후 앱 본체에서 삭제
    - 분기명 누락 sentinel 상수 참조 수정 (_WASAPI_AUTO → WASAPI_AUTO 등)
    - _on_file_select → on_file_select 이름 통일
    - handle_clear_file_list, handle_file_selection 추가 import

v1.0.43 (2026-04-25)
  - [리팩토링] app.py 모듈 분할 (2047줄 → 핵심 UI/이벤트만 남김)
    - patches.py: OS/SSL/Gradio 패치 추출
    - instances.py: recorder/transcriber/summarizer 공유 인스턴스 + 장치 sentinel 상수
    - worker.py: AutoTranscriptionWorker 추출
    - styles.py: CSS 문자열 추출
    - handlers_category.py: 분류 패널 헬퍼 및 핸들러
    - handlers_files.py: 파일 목록 헬퍼 및 핸들러
    - handlers_recording.py: 녹음/폴링/마이크 테스트 핸들러
    - handlers_ai.py: 전사/교정/요약/파이프라인 핸들러
  - [리팩토링] summarizer.py: _call_ollama() 헬퍼로 중복 예외처리 통합
  - [리팩토링] recorder.py: _run_wasapi_loopback/_run_wasapi_mix → _run_wasapi_thread() 공용 메서드


v1.0.42 (2026-04-25)
  - [수정] 소스 코드 점검 결과 버그 수정
    - app.py: handle_open_folder — os.startfile() Linux/macOS AttributeError
      → darwin: open, linux: xdg-open 으로 분기
    - app.py: _last_heartbeat 초기값 0.0 → float("inf")
      → 첫 폴링 전 타임아웃 조기 발생 방지, _watch() 내 수동 초기화 제거
    - recorder.py: _run_wasapi_loopback/_run_wasapi_mix Exception 시 stream 정리 추가
    - recorder.py: stop() — _chunk_timer.join() 추가 (콜백 완료 대기, 레이스 컨디션 방지)
    - transcriber.py: output_file.write_text() OSError → RuntimeError 변환
    - summarizer.py: summarize()/correct_transcript() write_text() OSError → RuntimeError 변환


v1.0.41 (2026-04-25)
  - [개선] 에러 로그 날짜별 파일 분리 — logs/YYYY-MM-DD.log
    - 기존 whispernote_error.log 단일 파일 → logs/ 폴더 날짜별 관리
    - .gitignore: logs/ 추가


v1.0.40 (2026-04-25)
  - [기능] 브라우저 탭 닫으면 CMD 창 자동 종료
    - /api/level heartbeat 30초 무응답 시 종료 트리거
    - 녹음 중 또는 전사/요약 처리 중이면 완료 후 종료
    - _start_heartbeat_watcher() daemon 스레드, 5초 주기 감시


v1.0.39 (2026-04-25)
  - [기능] 파일 목록 UI 구현 — 왼쪽 패널 gr.Audio 업로드 → 파일 목록+추가+재생 구조로 교체
    - 파일 목록(HTML) + JS 클릭/Ctrl 다중 선택 → selected_paths Textbox 연동
    - 분류 폴더 불러오기(↺), 목록 초기화(✕) 버튼
    - gr.File 다중 업로드 → 목록에 추가
    - 선택 파일 → audio_preview 재생 + uploaded_file(hidden) 갱신 → 기존 처리 버튼 호환
    - AutoTranscriptionWorker.enqueue_file() 추가 (다중 파일 자동 처리용)
    - _FILE_LIST_JS: 클릭/Ctrl+클릭 선택, MutationObserver 목록 갱신 시 선택 초기화


v1.0.38 (2026-04-25)
  - [개선] 전사 결과 헤더 행 레이아웃 — 원문/교정 라디오 우측 정렬, 여백 제거


v1.0.37 (2026-04-25)
  - [개선] Ollama 모델 상태 표시 개선
    - 성공 시 아무것도 표시 안 함 (Textbox 제거)
    - 연결 실패 시에만 작은 빨간 경고 텍스트 표시


v1.0.36 (2026-04-25)
  - [수정] 레벨 미터 바 길이 10칸 → 30칸으로 확장


v1.0.35 (2026-04-25)
  - [수정] 분류 설정 패널 라디오 선택 시 대/중/소분류 드롭다운 미표시 버그
    - on_panel_l1/l2/l3: value만 업데이트 → choices+value 함께 업데이트
    - Gradio가 choices 없이 value만 받으면 라벨을 못 찾는 문제 해결


v1.0.34 (2026-04-25)
  - [수정] 마이크 볼륨 기본값 1.0 → 3.0 (app.py 슬라이더 + recorder.py mic_gain)


v1.0.33 (2026-04-25)
  - [수정] 슬라이더 숫자 입력칸 너비 축소 (시스템 오디오 볼륨 레이블 2줄 방지)


v1.0.32 (2026-04-25)
  - [수정] 레벨미터/타이머 가로 비율 조정
    - 레벨미터 scale 4→2 (녹음 시작 버튼 너비와 정렬)
    - 타이머 scale 1→4 (녹음 종료 버튼 왼쪽부터 시작)
    - 타이머 white-space:nowrap 추가 (두 줄 잘림 방지)


v1.0.31 (2026-04-25)
  - [수정] app.py: import prompts 추가, summary_type 드롭다운 동적 로드
    - prompts.list_summary_types()로 choices 설정 (prompts/summary/ 폴더 기반)
    - demo.load에도 동적 갱신 추가


v1.0.30 (2026-04-25)
  - [수정] gr.HTML scale 파라미터 제거 (Gradio 4.x 미지원)
    - level_display, timer_display를 gr.Column으로 감싸 비율 조정


v1.0.29 (2026-04-25)
  - [개선] 요약/교정 프롬프트를 prompts/ 폴더 파일로 관리
    - prompts.py 신규: get_summary_prompt(), get_correction_prompt(), list_summary_types()
    - prompts/summary/{회의,면담,보고서 리뷰}.txt — 요약 프롬프트
    - prompts/correction/교정.txt — 교정 프롬프트
    - 앱 최초 실행 시 해당 파일 자동 생성, 직접 편집 후 즉시 반영
    - config.py: SUMMARY_PROMPT_TEMPLATE, SUMMARY_PROMPTS, CORRECTION_PROMPT_TEMPLATE 제거
    - summarizer.py: prompts 모듈로 import 변경


v1.0.28 (2026-04-25)
  - [기능] 자동 교정 후 자동 요약 활성화 (전사→교정→요약 완전 자동화)
    - AutoTranscriptionWorker._do_summarize() 주석 해제
    - 교정본이 있으면 교정본으로 요약, 없으면 원본 전사문 사용
    - handle_chunk_poll: summary 결과 처리 + _poll_outputs 확장
    - btn_transcribe 체인: .then(handle_correct).then(handle_summarize)
  - [개선] UI 레이아웃 대폭 개편
    - 분류(대/중/소) 전체 너비 한 줄로 최상단 배치
    - 녹음 섹션 전체 너비 카드로 이동
      - 입력장치·볼륨슬라이더·자동분할·요약구분 한 줄
      - 버튼 한 줄, 레벨미터+타이머 한 줄, 상태+파일경로 한 줄
    - 전사 파일 병합 UI 제거 (자동 병합으로 불필요)
    - 하단 2컬럼: 왼쪽(업로드+Ollama+버튼) / 오른쪽(결과)


v1.0.27 (2026-04-24)
  - [개선] 혼합 녹음 마이크 음량 자동 보정
    - _mix_mic_system(): 마이크 RMS가 시스템 오디오 절반 미만이면 최대 8배 자동 증폭
    - stop(), _do_chunk_split() 모두 _mix_mic_system() 호출로 통일
    - mic_gain_slider max: 4.0 -> 10.0 (수동 증폭 범위 확대)


v1.0.26 (2026-04-24)
  - [수정] transcriber.py: Whisper 반복 환각 방지
    - condition_on_previous_text: True -> False (무음 구간 반복 생성 차단)
    - compression_ratio_threshold: 2.4 -> 1.8 (반복 텍스트 더 공격적으로 필터)
    - no_speech_threshold: 0.6 -> 0.5 (무음 판별 민감도 상향)


v1.0.25 (2026-04-24)
  - [수정] (원격) 원격회의 마이크 테스트: RDP 마이크만 -> RDP+시스템 혼합 테스트


v1.0.24 (2026-04-24)
  - [개선] (PC) 원격회의 마이크 테스트: 마이크+시스템 오디오 동시 테스트
    - start_test(mixed=True): 마이크 InputStream + WASAPI 루프백 동시 실행
    - _run_wasapi_mix: self.testing 중에도 루프 유지
    - stop_test(): mix 스레드/데이터 정리 추가


v1.0.23 (2026-04-24)
  - [수정] (PC) 원격회의 마이크 테스트: WASAPI 테스트로 복원
    - 마이크 테스트 = 시스템 오디오 경로 검증 (레벨미터 반응 복원)
    - 실제 녹음은 기본 마이크 + WASAPI 혼합 유지


v1.0.22 (2026-04-24)
  - [개선] (PC) 원격회의 옵션: WASAPI 전용 -> 마이크+시스템 혼합 모드로 교체
    - 라벨: "(PC) 🎧 원격회의" -> "(PC) 🎙+🎧 원격회의"
    - 녹음: wasapi_loopback 전용 -> mixed=True(기본 마이크 + WASAPI 혼합)
    - 마이크 테스트: WASAPI 테스트 -> 기본 마이크 테스트로 변경
    - 게인 슬라이더: 마이크+시스템 볼륨 둘 다 표시


v1.0.21 (2026-04-24)
  - [수정] recorder.py: WASAPI 스레드 COM 초기화 누락 (Error 0x800401f0)
    - _run_wasapi_loopback, _run_wasapi_mix: CoInitialize/CoUninitialize 추가
    - 원격회의 마이크 테스트/녹음 시 즉시 실패하던 문제 해결


v1.0.20 (2026-04-24)
  - [개선] 전사 완료 후 자동 교정 실행 (교정 버튼 제거)
    - btn_correct 버튼 UI에서 삭제
    - btn_transcribe: 전사 완료 후 .then()으로 handle_correct 자동 연결
    - handle_pipeline: 전사→교정→요약 순서로 변경 (교정본으로 요약)
    - handle_summarize: correction_output 우선 사용, 없으면 transcript_output 사용


v1.0.19 (2026-04-24)
  - [개선] 전사 진행률 실시간 반영 (0.1% 단위)
    - transcriber.py: on_progress(pct, msg) 시그니처로 변경
    - 오디오 시간 기반 실제 진행률 계산 (s.end / duration)
    - 단계별 구간: 모델로딩 0-5%, 전사 5-75%, 정렬 75-88%, 화자분리 88-97%, 저장 97-100%
    - 터미널 출력은 5% 단위 유지 (과도한 출력 방지)
  - app.py: on_progress 콜백 시그니처 통일 (lambda pct, m)
    - handle_pipeline: 전사 구간 0-75% 로 스케일


v1.0.18 (2026-04-24)
  - [수정] Windows CMD Quick Edit Mode 비활성화
    - 창 클릭 시 프로세스 일시정지 문제 해결
    - app.py, download_whisper.py: Python 시작 시 SetConsoleMode로 ENABLE_QUICK_EDIT 제거
    - install.bat, install_whisper.bat: Python 준비 직후 동일 처리


v1.0.17 (2026-04-24)
  - [개선] 전사/교정 결과 UI 통합 — 원문/교정 radio로 전환
    - 전사 결과 + 교정 결과 별도 칸 → text_display 단일 텍스트박스
    - view_radio(원문/교정) 로 전환, 교정본 생성 시 자동으로 "교정" 선택
    - 요약 대상 자동 연동 — 현재 보이는 텍스트(view_radio 선택)로 요약
    - transcript_source_radio 제거, handle_summarize 단순화


v1.0.16 (2026-04-24)
  - [수정] config.py: CORRECTION_PROMPT_TEMPLATE 개정
    - 형식 유지 강조: 타임스탬프·화자 레이블 원문 그대로
    - 교정 범위 축소: 단어·맞춤법·띄어쓰기만, 문장구조/어순/추임새 금지
    - 줄 합치기·나누기 금지 명시


v1.0.15 (2026-04-24)
  - [수정] requirements.txt: librosa 추가 (resemblyzer --no-deps 설치로 누락됨)
  - [수정] requirements.txt: transformers>=4.48.0 명시
    - Wav2Vec2ForCTC 정렬 모델 임포트 오류 해결
    - pyannote.audio==3.4.0 (>=4.39.1) + whisperx (>=4.48.0) 동시 충족


v1.0.14 (2026-04-24)
  - [수정] install.bat: PyTorch CUDA 버전 cu130(없는버전) → cu124 로 수정
  - [수정] install.bat: torch 체크를 CUDA 가용 여부까지 확인 (CPU 전용 빌드면 재설치)
  - [개선] app.py: GPU 진단 메시지 세분화
    - CPU 전용 빌드: "install.bat 재실행" 안내
    - CUDA 빌드이나 GPU 미인식: "nvidia-smi 확인" 안내
    - 정상: GPU명 + CUDA 버전 표시


v1.0.13 (2026-04-23)
  - [수정] download_whisper.py: 회사 프록시 SSL 인증서 우회 패치 추가
    - ssl.SSLCertVerificationError: self-signed certificate 오류 해결
    - HF_HUB_DISABLE_SSL_VERIFICATION, REQUESTS_CA_BUNDLE 환경변수 설정
    - ssl._create_default_https_context 패치, requests.Session verify=False
    - app.py와 동일한 SSL 우회 방식 적용
  - [기능] install_whisper.bat: Whisper 모델 단독 재다운로드 배치 파일 추가
  - [개선] download_whisper.py: --log Tee 로깅, 진단 헤더, Method1/2 fallback


v1.0.12 (2026-04-23)


v1.0.11 (2026-04-23)
  - [기능] 자동 교정 — 모든 파트 전사 완료 후 통합 전사문 자동 교정 (자동 요약 주석처리)
  - [개선] 모델 다운로드 진행률 0.1% 단위로 세분화 — 50자 막대, X.X% 소수점 표시
    [다운로드] ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  16.0%  256.0/1600MB
  - [개선] install.bat PyTorch/requirements.txt 설치 시 pip 진행바 표시 (기존 -q 제거)
  - app.py: handle_chunk_poll 교정 결과 반영 (summary→correction 타입)
  - app.py: _poll_outputs 교정 출력 컴포넌트 연결 (correction_output, corrected_file_path)


v1.0.10 (2026-04-23)
  - [기능] 자동 처리 대기열 실시간 표시 — "🔄 처리 중 / ⏳ 대기 중" UI 패널
  - [기능] 자동 요약 — 모든 파트 전사 완료 후 통합 전사문 자동 요약, 결과 UI 반영
  - [개선] 모델 다운로드 진행률 터미널 출력 — tqdm 교체로 5% 단위 막대 표시
    [다운로드] ████████░░ 40%  640/1600MB  model.bin
  - app.py: AutoTranscriptionWorker 재설계 (대기열 라벨, finalize job, 자동 요약)
  - app.py: handle_chunk_poll 9-output (+ summary_output, summary_file_path, queue_status)
  - app.py: btn_start에 ollama_model, summary_type 입력 추가


v1.0.9 (2026-04-23)
  - [진단] transcriber.py: 각 단계마다 터미널 print 출력
    모델 로딩/GPU 여부/오디오 길이/세그먼트 진행/정렬/화자분리/저장 경로
  - [진단] app.py: 시작 시 GPU 상태 출력 (CUDA 가능 여부, CPU 폴백 시 경고)


v1.0.8 (2026-04-22)
  - [기능] 자동 전사 — 청크 분할 및 녹음 종료 시 백그라운드 자동 전사 시작
  - 파트별 전사파일: {base}_part01_transcript.txt 등 별도 저장
  - 통합 전사파일: {base}_transcript.txt (파트 완료마다 누적 갱신)
  - 파트 헤더 포함: [파트 N - HH:MM:SS ~ HH:MM:SS]
  - 전사 진행 중 녹음 완료 시 전사 끝날 때까지 타이머 유지, 완료 후 자동 종료
  - 결과 실시간 UI 반영 (transcript_output / transcript_file_path / pipeline_status)
  - recorder.py: _cumulative_secs, _pending_transcriptions 추가
  - app.py: AutoTranscriptionWorker 클래스, handle_chunk_poll 6-output 확장


v1.0.7 (2026-04-22)
  - [개선] 요약 구분 드롭다운 위치 변경 — 분류 행 → 요약 버튼 바로 위


v1.0.6 (2026-04-22)
  - [기능] 요약 구분 드롭다운 추가 — 회의 / 면담 / 보고서 리뷰
  - 분류 행(소분류 옆)에 위치, 선택 시 해당 프롬프트로 요약
  - config.py: SUMMARY_PROMPTS 딕셔너리 추가 (현재 3가지 동일 프롬프트, 추후 상세 분리)
  - summarizer.py: summarize(summary_type) 파라미터 추가
  - app.py: handle_summarize/handle_pipeline에 summary_type 연결


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
