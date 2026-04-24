from pathlib import Path

# 경로 설정
BASE_DIR = Path(__file__).parent
RECORDINGS_DIR = BASE_DIR / "recordings"
OUTPUTS_DIR = BASE_DIR / "outputs"
CATEGORIES_FILE = BASE_DIR / "categories.json"

# 오디오 설정
SAMPLE_RATE = 16000
CHANNELS = 1

# 입력 소스: "microphone" (기본 마이크) 또는 "loopback" (시스템 오디오, Zoom/Teams 등)
# loopback 사용 시 Windows 사운드 설정에서 "Stereo Mix" 활성화 필요
INPUT_SOURCE = "microphone"
LOOPBACK_DEVICE_INDEX = None  # None = 자동 감지, 또는 장치 인덱스(int) 지정

# WhisperX 설정
WHISPER_MODEL          = "large-v3-turbo"  # tiny / base / small / medium / large-v3 / large-v3-turbo
WHISPER_LANGUAGE       = "ko"              # 전사 언어
WHISPER_DEVICE         = "cuda"            # "cuda" (GPU) 또는 "cpu"
WHISPER_COMPUTE_TYPE   = "float16"         # GPU: "float16" / CPU: "int8"
WHISPER_BATCH_SIZE     = 16
WHISPER_BEAM_SIZE      = 10               # 높을수록 정확도 향상 (기본 5)
WHISPER_VAD_FILTER     = True             # 무음/잡음 구간 hallucination 방지
WHISPER_INITIAL_PROMPT = "다음은 한국어 회의 녹음입니다."  # 한국어 인식률 향상

RECORDING_CHUNK_MINUTES = 30     # 자동 분할 간격(분). 0 = 비활성화

# 화자 분리 (Speaker Diarization)
# resemblyzer + SpectralClustering 기반 — HuggingFace 불필요, 완전 오프라인
# (resemblyzer 가중치 ~17MB 는 최초 실행 시 자동 다운로드 후 캐시에 저장됨)
ENABLE_DIARIZATION = True
NUM_SPEAKERS = None    # None = 자동 감지, 숫자 지정 시 해당 화자 수로 고정 (예: 2)

# Ollama 설정
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "exaone3.5:latest"   # 기본 모델 (UI에서 변경 가능)
OLLAMA_TIMEOUT = 600                 # 요약 응답 대기 시간(초) - 2시간 회의 분량 대응

# 요약 프롬프트
SUMMARY_PROMPT_TEMPLATE = """다음은 회의 전사문입니다. 아래 형식으로 요약해주세요.

## 핵심 내용
- 주요 논의 사항을 bullet point로 정리

## 결정 사항
- 회의에서 결정된 사항 정리 (없으면 "없음")

## 액션아이템
- 구체적인 액션아이템과 담당자 정리 (없으면 "없음")

---
전사문:
{transcript}
"""

# 요약 구분별 프롬프트 (추후 각각 상세 작성 예정, 현재 동일)
SUMMARY_PROMPTS: dict[str, str] = {
    "회의":        SUMMARY_PROMPT_TEMPLATE,
    "면담":        SUMMARY_PROMPT_TEMPLATE,
    "보고서 리뷰": SUMMARY_PROMPT_TEMPLATE,
}

# 전사 교정 프롬프트
CORRECTION_PROMPT_TEMPLATE = """너는 STT 전사 오류 교정기다. 맞춤법·단어 수준의 오류만 수정한다.

규칙:
1. 각 줄의 형식([화자] [시작s - 끝s] 텍스트)을 절대 변경하지 말 것
2. 타임스탬프, 화자 레이블은 원문 그대로 유지할 것
3. STT가 잘못 받아 적은 단어·맞춤법·띄어쓰기만 수정할 것
4. 문장 구조, 어순, 추임새는 건드리지 말 것
5. 줄을 합치거나 나누지 말 것
6. 수정이 불필요한 줄은 그대로 출력할 것
7. 설명이나 주석을 추가하지 말 것

---
전사문:
{transcript}
"""
