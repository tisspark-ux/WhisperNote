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


class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.audio_data: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None
        self.lock = threading.Lock()
        self.current_file: Path | None = None
        self._actual_samplerate: int = SAMPLE_RATE

    # ------------------------------------------------------------------
    # 장치 관련
    # ------------------------------------------------------------------

    def _find_loopback_device(self) -> int | None:
        """WASAPI loopback 장치(시스템 오디오)를 자동 탐색."""
        devices = sd.query_devices()
        keywords = ("loopback", "stereo mix", "what u hear", "wavout")
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                name_lower = dev["name"].lower()
                if any(kw in name_lower for kw in keywords):
                    return i
        return None

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

        # 기본 마이크: 기본 장치가 유효한지 먼저 확인
        try:
            info = sd.query_devices(None, "input")
            if info.get("index", -1) >= 0:
                return None  # 기본 입력 장치 정상
        except Exception:
            pass

        # 기본 장치 없음 → 사용 가능한 첫 번째 입력 장치 자동 선택
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                return i

        available = self.list_devices()
        raise RuntimeError(
            "마이크를 찾을 수 없습니다.\n"
            "설정 탭 > [장치 목록 조회] 버튼으로 사용 가능한 장치를 확인하세요.\n"
            f"현재 감지된 입력 장치:\n{available}"
        )

    # ------------------------------------------------------------------
    # 녹음 제어
    # ------------------------------------------------------------------

    def start(self) -> tuple[str | None, str]:
        """녹음 시작. (파일경로 | None, 상태 메시지) 반환."""
        if self.recording:
            return None, "이미 녹음 중입니다."

        try:
            device = self._resolve_device()

            # 장치 기본 샘플레이트 확인
            dev_info = sd.query_devices(device, "input")
            if dev_info is None:
                raise RuntimeError("입력 장치를 찾을 수 없습니다.")
            self._actual_samplerate = int(dev_info["default_samplerate"])

            self.audio_data = []
            self.recording = True

            def _callback(indata: np.ndarray, frames: int, time, status):
                if self.recording:
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
            if INPUT_SOURCE == "loopback":
                source_label = f"시스템 오디오 (loopback): {device_name}"
            else:
                source_label = f"마이크: {device_name}"
            return str(self.current_file), f"녹음 시작 — {source_label}"

        except Exception as exc:
            self.recording = False
            self.stream = None
            return None, f"녹음 시작 실패: {exc}"

    def stop(self) -> tuple[str | None, str]:
        """녹음 종료 후 WAV 저장. (파일경로 | None, 상태 메시지) 반환."""
        if not self.recording:
            return None, "녹음 중이 아닙니다."

        self.recording = False

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
                lines.append(f"[{i}] {dev['name']} (SR: {int(dev['default_samplerate'])}Hz)")
        return "\n".join(lines) if lines else "입력 장치 없음"
