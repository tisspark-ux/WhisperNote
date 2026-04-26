"""instances.py — 앱 전역 공유 인스턴스 및 장치 sentinel 상수.

여러 핸들러 모듈에서 동일 인스턴스를 참조해야 하므로
한 곳에서 생성 후 공유한다.
"""
from core.recorder import AudioRecorder, is_loopback_device_name, is_rdp_device_name
from core.transcriber import Transcriber
from core.summarizer import Summarizer

recorder    = AudioRecorder()
transcriber = Transcriber()
summarizer  = Summarizer()

# 입력 장치 선택 sentinel 값 (드롭다운 인덱스 대신 특수 의미)
LOOPBACK_AUTO = -2   # WASAPI Stereo Mix 자동 감지
REMOTE_AUTO   = -3   # RDP 원격 마이크 자동 감지
WASAPI_AUTO   = -4   # WASAPI 마이크+시스템 믹스 (원격회의 PC 모드)
MIX_AUTO      = -5   # RDP 마이크+시스템 믹스 (원격회의 원격 모드)
