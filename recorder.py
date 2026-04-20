import threading
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from config import (
    CHANNELS,
    INPUT_SOURCE,
    LOOPBACK_DEVICE_INDEX,
    RECORDINGS_DIR,
    SAMPLE_RATE,
)

RECORDINGS_DIR.mkdir(exist_ok=True)

_LOOPBACK_KEYWORDS = (
    "loopback",
    "stereo mix",
    "what u hear",
    "wavout",
    "wave out",
    "재생 소리",
    "스테레오 믹스",
    "출력 믹스",
    "virtual audio cable",
    "voicemeeter",
    "mix output",
)


def is_loopback_device_name(name: str) -> bool:
    """장치 이름이 루프백/시스템 오디오 장치인지 키워드로 판별."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in _LOOPBACK_KEYWORDS)


class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.paused = False
        self.testing = False
        self.audio_data: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None
        self.lock = threading.Lock()
        self.current_file: Path | None = None
        self._actual_samplerate: int = SAMPLE_RATE

    # ------------------------------------------------------------------
    # 장치 관련
    # ------------------------------------------------------------------

    def find_loopback_device(self) -> tuple[int, str] | tuple[None, None]:
        """루프백 장치 인덱스와 이름 반환. 없으면 (None, None)."""
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0 and is_loopback_device_name(dev["name"]):
                return i, dev["name"]
        return None, None

    def _find_loopback_device(self) -> int | None:
        idx, _ = self.find_loopback_device()
        return idx

    def _resolve_device(self) -> int | None:
        """설정에 따라 실제 사용할 입력 장치 인덱스를 반환."""
        if INPUT_SOURCE == "loopback":
            idx = LOOPBACK_DEVICE_INDEX if LOOPBACK_DEVICE_INDEX is not None else self._find_loopback_device()
            if idx is None:
                raise RuntimeError(
                    "WASAPI loopback 장치를 찾을 수 없습니다.\n"
                    "Windows 사운드 설정 → 녹음 탭 → 'Stereo Mix' 활성화 후 재시도하거나,\n"
                    "config.py 의 INPUT_SOURCE 를 'microphone' 으로 변경하세요."
                )
            return idx

        try:
            info = sd.query_devices(None, "input")
            if info.get("index", -1) >= 0:
                return None
        except Exception:
            pass

        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                return i

        available = self.list_devices()
        raise RuntimeError(
            "마이크를 찾을 수 없습니다.\n"
            "설정 탭 > [장치 목록 조회] 버튼으로 사용 가능한 장치를 확인하세요.\n"
            f"현재 감지된 입력 장치:\n{available}"
        )

    def _open_input_stream(self, device_override) -> tuple[int | None, dict]:
        """공통 스트림 열기 로직. (device_index, dev_info) 반환."""
        device = device_override if device_override is not None else self._resolve_device()
        dev_info = sd.query_devices(device, "input")
        if dev_info is None:
            raise RuntimeError("입력 장치를 찾을 수 없습니다.")
        self._actual_samplerate = int(dev_info["default_samplerate"])
        return device, dev_info

    # ------------------------------------------------------------------
    # 레벨 측정
    # ------------------------------------------------------------------

    def get_level(self) -> float:
        """현재 오디오 레벨 0–100. 녹음 중(일시정지 제외) 또는 테스트 중일 때 동작."""
        if self.paused:
            return 0.0
        if not (self.recording or self.testing):
            return 0.0
        with self.lock:
            if not self.audio_data:
                return 0.0
            recent = self.audio_data[-8:]
        chunk = np.concatenate(recent)
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        return min(100.0, rms * 1200)

    # ------------------------------------------------------------------
    # 마이크 테스트 (저장 없이 레벨만 측정)
    # ------------------------------------------------------------------

    def start_test(self, device_override=None) -> str:
        """마이크 테스트 시작. 오디오를 저장하지 않고 레벨만 측정."""
        if self.recording:
            return "녹음 중에는 테스트할 수 없습니다."
        if self.testing:
            return self.stop_test()

        try:
            device, dev_info = self._open_input_stream(device_override)
            self.audio_data = []
            self.testing = True

            def _callback(indata: np.ndarray, frames: int, time, status):
                if self.testing:
                    with self.lock:
                        self.audio_data.append(indata.copy())
                        if len(self.audio_data) > 20:
                            self.audio_data.pop(0)

            self.stream = sd.InputStream(
                device=device,
                channels=CHANNELS,
                samplerate=self._actual_samplerate,
                callback=_callback,
                dtype="float32",
            )
            self.stream.start()
            device_name = dev_info.get("name", "알 수 없음")
            return f"마이크 테스트 중 — {device_name}"
        except Exception as exc:
            self.testing = False
            self.stream = None
            return f"테스트 실패: {exc}"

    def stop_test(self) -> str:
        """마이크 테스트 종료."""
        if not self.testing:
            return "테스트 중이 아닙니다."
        self.testing = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.audio_data = []
        return "마이크 테스트 종료"

    # ------------------------------------------------------------------
    # 녹음 제어
    # ------------------------------------------------------------------

    def start(self, device_override=None) -> tuple[str | None, str]:
        """녹음 시작. 테스트 중이면 자동 종료 후 녹음 시작."""
        if self.testing:
            self.stop_test()
        if self.recording:
            return None, "이미 녹음 중입니다."

        try:
            device, dev_info = self._open_input_stream(device_override)
            self.audio_data = []
            self.paused = False
            self.recording = True

            def _callback(indata: np.ndarray, frames: int, time, status):
                if self.recording and not self.paused:
                    with self.lock:
                        self.audio_data.append(indata.copy())

            self.stream = sd.InputStream(
                device=device,
                channels=CHANNELS,
                samplerate=self._actual_samplerate,
                callback=_callback,
                dtype="float32",
            )
            self.stream.start()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_file = RECORDINGS_DIR / f"{timestamp}.wav"

            device_name = dev_info.get("name", "알 수 없음")
            if INPUT_SOURCE == "loopback" or is_loopback_device_name(device_name):
                source_label = f"시스템 오디오 (loopback): {device_name}"
            else:
                source_label = f"마이크: {device_name}"
            return str(self.current_file), f"녹음 시작 — {source_label}"

        except Exception as exc:
            self.recording = False
            self.paused = False
            self.stream = None
            return None, f"녹음 시작 실패: {exc}"

    def pause(self) -> str:
        """녹음 일시정지."""
        if not self.recording:
            return "녹음 중이 아닙니다."
        if self.paused:
            return "이미 일시정지 중입니다."
        self.paused = True
        return "일시정지됨 — 재개하려면 ▶ 재개 버튼을 누르세요"

    def resume(self) -> str:
        """녹음 재개."""
        if not self.recording:
            return "녹음 중이 아닙니다."
        if not self.paused:
            return "일시정지 상태가 아닙니다."
        self.paused = False
        return "녹음 재개됨"

    def stop(self) -> tuple[str | None, str]:
        """녹음 종료 후 WAV 저장."""
        if not self.recording:
            return None, "녹음 중이 아닙니다."

        self.recording = False
        self.paused = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            return None, "녹음된 데이터가 없습니다."

        with self.lock:
            audio_array = np.concatenate(self.audio_data, axis=0)

        sf.write(str(self.current_file), audio_array, self._actual_samplerate)
        duration = len(audio_array) / self._actual_samplerate
        return str(self.current_file), f"녹음 완료: {duration:.1f}초 ({self.current_file.name})"

    # ------------------------------------------------------------------
    # 장치 목록 조회
    # ------------------------------------------------------------------

    def list_devices(self) -> str:
        """입력 가능한 오디오 장치 목록을 문자열로 반환."""
        devices = sd.query_devices()
        lines = []
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                tag = " [루프백]" if is_loopback_device_name(dev["name"]) else ""
                lines.append(f"[{i}] {dev['name']}{tag} (SR: {int(dev['default_samplerate'])}Hz)")
        return "\n".join(lines) if lines else "입력 장치 없음"
