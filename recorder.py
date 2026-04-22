import threading
import time as _time_mod
from collections import deque
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

_RDP_KEYWORDS = (
    "remote audio",
    "원격 오디오",
    "rdp",
    "원격 마이크",
    "원격 입력",
)


def is_loopback_device_name(name: str) -> bool:
    """장치 이름이 루프백/시스템 오디오 장치인지 키워드로 판별."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in _LOOPBACK_KEYWORDS)


def is_rdp_device_name(name: str) -> bool:
    """장치 이름이 RDP 원격 오디오 장치인지 키워드로 판별."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in _RDP_KEYWORDS)


def _fmt_time(secs: float) -> str:
    s = max(0, int(secs))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


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
        self._chunk_seconds: int = 0
        self._chunk_timer: threading.Timer | None = None
        self._part_index: int = 0
        self._base_timestamp: str = ""
        self._wav_dir_ref: Path | None = None
        self._notify_queue: deque[str] = deque()
        self._wasapi_thread: threading.Thread | None = None
        self._wasapi_error: str | None = None
        self._mix_audio_data: list[np.ndarray] = []
        self._mix_thread: threading.Thread | None = None
        self._mix_error: str | None = None
        self._is_mixed: bool = False
        self.mic_gain: float = 1.0
        self.system_gain: float = 1.0
        self._recording_start: float | None = None
        self._part_start: float | None = None
        self._paused_duration: float = 0.0
        self._part_paused_duration: float = 0.0
        self._pause_start: float | None = None
        self._cumulative_secs: float = 0.0
        self._pending_transcriptions: deque = deque()

    # ------------------------------------------------------------------
    # 장치 관련
    # ------------------------------------------------------------------

    def find_loopback_device(self) -> tuple[int, str] | tuple[None, None]:
        """루프백 장치 인덱스와 이름 반환. 없으면 (None, None)."""
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0 and is_loopback_device_name(dev["name"]):
                return i, dev["name"]
        return None, None

    def get_wasapi_speaker_name(self) -> str | None:
        """soundcard로 기본 출력 장치 이름 반환. 실패 시 None."""
        try:
            import soundcard as sc
            return sc.default_speaker().name
        except Exception:
            return None

    def _run_wasapi_loopback(self):
        """soundcard WASAPI 루프백 녹음/테스트 스레드."""
        try:
            import soundcard as sc
        except ImportError:
            self._wasapi_error = "soundcard 미설치. install.bat 재실행 또는 pip install soundcard"
            return
        CHUNK = 1024
        try:
            speaker = sc.default_speaker()
            loopback_mic = sc.get_microphone(speaker.id, include_loopback=True)
            with loopback_mic.recorder(samplerate=self._actual_samplerate, channels=CHANNELS) as rec:
                while self.recording or self.testing:
                    data = rec.record(numframes=CHUNK)
                    if self.paused:
                        continue
                    with self.lock:
                        self.audio_data.append(np.clip(data * self.system_gain, -1.0, 1.0))
                        if self.testing and len(self.audio_data) > 20:
                            self.audio_data.pop(0)
        except Exception as exc:
            self._wasapi_error = str(exc)
            self.recording = False
            self.testing = False

    def _run_wasapi_mix(self):
        """혼합 녹음 시 WASAPI 루프백 스레드 (_mix_audio_data에 저장)."""
        try:
            import soundcard as sc
        except ImportError:
            self._mix_error = "soundcard 미설치"
            return
        CHUNK = 1024
        try:
            speaker = sc.default_speaker()
            loopback_mic = sc.get_microphone(speaker.id, include_loopback=True)
            with loopback_mic.recorder(samplerate=self._actual_samplerate, channels=CHANNELS) as rec:
                while self.recording:
                    data = rec.record(numframes=CHUNK)
                    if self.paused:
                        continue
                    with self.lock:
                        self._mix_audio_data.append(np.clip(data * self.system_gain, -1.0, 1.0))
        except Exception as exc:
            self._mix_error = str(exc)
            self.recording = False

    def find_rdp_device(self) -> tuple[int, str] | tuple[None, None]:
        """RDP 원격 오디오 입력 장치 검색. 입력 채널 있는 장치 우선 반환."""
        candidates = []
        for i, dev in enumerate(sd.query_devices()):
            if is_rdp_device_name(dev["name"]):
                candidates.append((i, dev["name"], dev["max_input_channels"]))
        if not candidates:
            return None, None
        usable = [(i, name) for i, name, ch in candidates if ch > 0]
        if usable:
            return usable[0]
        return candidates[0][0], candidates[0][1]

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
            if self._is_mixed:
                recent = self.audio_data[-8:] + self._mix_audio_data[-8:]
            else:
                recent = self.audio_data[-8:]
            if not recent:
                return 0.0
        chunk = np.concatenate(recent)
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        return min(100.0, rms * 1200)

    def get_elapsed(self) -> dict:
        """녹음 경과 시간 반환. 일시정지 시간 제외."""
        if not self.recording or self._recording_start is None:
            return {"total": None, "part": None, "part_index": 1, "has_parts": False}
        now = _time_mod.monotonic()
        pause_adj = (now - self._pause_start) if (self.paused and self._pause_start) else 0.0
        total = now - self._recording_start - self._paused_duration - pause_adj
        part  = now - self._part_start - self._part_paused_duration - pause_adj
        return {
            "total": _fmt_time(total),
            "part":  _fmt_time(part),
            "part_index": self._part_index,
            "has_parts": self._chunk_seconds > 0,
        }

    # ------------------------------------------------------------------
    # 마이크 테스트 (저장 없이 레벨만 측정)
    # ------------------------------------------------------------------

    def start_test(self, device_override=None, wasapi_loopback: bool = False) -> str:
        """마이크 테스트 시작. 오디오를 저장하지 않고 레벨만 측정."""
        if self.recording:
            return "녹음 중에는 테스트할 수 없습니다."
        if self.testing:
            return self.stop_test()

        if wasapi_loopback:
            self.audio_data = []
            self.testing = True
            self._wasapi_error = None
            self._actual_samplerate = SAMPLE_RATE
            self._wasapi_thread = threading.Thread(target=self._run_wasapi_loopback, daemon=True)
            self._wasapi_thread.start()
            import time as _t; _t.sleep(0.4)
            if self._wasapi_error:
                self.testing = False
                return f"테스트 실패: {self._wasapi_error}"
            speaker_name = self.get_wasapi_speaker_name() or "기본 출력"
            return f"시스템 오디오 테스트 중 (WASAPI) — {speaker_name}"

        try:
            device, dev_info = self._open_input_stream(device_override)
            self.audio_data = []
            self.testing = True

            def _callback(indata: np.ndarray, frames: int, time, status):
                if self.testing:
                    with self.lock:
                        self.audio_data.append(np.clip(indata * self.mic_gain, -1.0, 1.0))
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
        if self._wasapi_thread:
            self._wasapi_thread.join(timeout=2)
            self._wasapi_thread = None
        self.audio_data = []
        return "마이크 테스트 종료"

    # ------------------------------------------------------------------
    # 녹음 제어
    # ------------------------------------------------------------------

    def start(self, device_override=None, output_dir=None, chunk_minutes: int = 0, wasapi_loopback: bool = False, mixed: bool = False) -> tuple[str | None, str]:
        """녹음 시작. 테스트 중이면 자동 종료 후 녹음 시작."""
        if self.testing:
            self.stop_test()
        if self.recording:
            return None, "이미 녹음 중입니다."

        # 공통 파일 경로 초기화
        wav_dir = output_dir if output_dir is not None else RECORDINGS_DIR
        wav_dir.mkdir(parents=True, exist_ok=True)
        self._wav_dir_ref = wav_dir
        self._base_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._chunk_seconds = max(0, int(chunk_minutes)) * 60
        self._part_index = 1
        self._notify_queue.clear()
        self._pending_transcriptions = deque()
        self._cumulative_secs = 0.0
        self.audio_data = []
        self._mix_audio_data = []
        self._is_mixed = False
        self.paused = False
        self._recording_start = _time_mod.monotonic()
        self._part_start      = _time_mod.monotonic()
        self._paused_duration = 0.0
        self._part_paused_duration = 0.0
        self._pause_start = None

        if self._chunk_seconds > 0:
            self.current_file = wav_dir / f"{self._base_timestamp}_part{self._part_index:02d}.wav"
        else:
            self.current_file = wav_dir / f"{self._base_timestamp}.wav"

        if mixed:
            try:
                device, dev_info = self._open_input_stream(device_override)
                self._mix_error = None
                self._is_mixed = True
                self.recording = True

                def _mix_mic_callback(indata: np.ndarray, frames: int, time, status):
                    if self.recording and not self.paused:
                        with self.lock:
                            self.audio_data.append(np.clip(indata * self.mic_gain, -1.0, 1.0))

                self.stream = sd.InputStream(
                    device=device,
                    channels=CHANNELS,
                    samplerate=self._actual_samplerate,
                    callback=_mix_mic_callback,
                    dtype="float32",
                )
                self.stream.start()
                self._mix_thread = threading.Thread(target=self._run_wasapi_mix, daemon=True)
                self._mix_thread.start()
                import time as _t; _t.sleep(0.4)
                if self._mix_error:
                    self.recording = False
                    self._is_mixed = False
                    self.stream.stop(); self.stream.close(); self.stream = None
                    self._mix_thread.join(timeout=2); self._mix_thread = None
                    return None, f"WASAPI 혼합 시작 실패: {self._mix_error}"
                if self._chunk_seconds > 0:
                    self._schedule_chunk_timer()
                device_name = dev_info.get("name", "알 수 없음")
                speaker_name = self.get_wasapi_speaker_name() or "기본 출력"
                return str(self.current_file), f"녹음 시작 — 혼합 ({device_name} + WASAPI {speaker_name})"
            except Exception as exc:
                self.recording = False
                self._is_mixed = False
                self.stream = None
                return None, f"녹음 시작 실패: {exc}"

        if wasapi_loopback:
            self._actual_samplerate = SAMPLE_RATE
            self._wasapi_error = None
            self.recording = True
            self._wasapi_thread = threading.Thread(target=self._run_wasapi_loopback, daemon=True)
            self._wasapi_thread.start()
            import time as _t; _t.sleep(0.4)
            if self._wasapi_error:
                self.recording = False
                return None, f"WASAPI 루프백 시작 실패: {self._wasapi_error}"
            if self._chunk_seconds > 0:
                self._schedule_chunk_timer()
            speaker_name = self.get_wasapi_speaker_name() or "기본 출력"
            return str(self.current_file), f"녹음 시작 — 시스템 오디오 WASAPI ({speaker_name})"

        try:
            device, dev_info = self._open_input_stream(device_override)
            self.recording = True

            def _callback(indata: np.ndarray, frames: int, time, status):
                if self.recording and not self.paused:
                    with self.lock:
                        self.audio_data.append(np.clip(indata * self.mic_gain, -1.0, 1.0))

            self.stream = sd.InputStream(
                device=device,
                channels=CHANNELS,
                samplerate=self._actual_samplerate,
                callback=_callback,
                dtype="float32",
            )
            self.stream.start()

            if self._chunk_seconds > 0:
                self._schedule_chunk_timer()

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

    # ------------------------------------------------------------------
    # 자동 분할
    # ------------------------------------------------------------------

    def _schedule_chunk_timer(self):
        if self._chunk_seconds <= 0 or not self.recording:
            return
        self._chunk_timer = threading.Timer(self._chunk_seconds, self._do_chunk_split)
        self._chunk_timer.daemon = True
        self._chunk_timer.start()

    def _do_chunk_split(self):
        if not self.recording:
            return
        with self.lock:
            mic_data = list(self.audio_data)
            self.audio_data = []
            mix_data = list(self._mix_audio_data)
            self._mix_audio_data = []
        if mic_data or mix_data:
            if self._is_mixed and mix_data:
                mic_arr = np.concatenate(mic_data, axis=0) if mic_data else None
                mix_arr = np.concatenate(mix_data, axis=0)
                if mic_arr is not None:
                    min_len = min(len(mic_arr), len(mix_arr))
                    audio_array = np.clip(mic_arr[:min_len] + mix_arr[:min_len], -1.0, 1.0)
                else:
                    audio_array = mix_arr
            else:
                audio_array = np.concatenate(mic_data, axis=0)
            saved_path = self.current_file
            current_part = self._part_index
            duration_secs = len(audio_array) / self._actual_samplerate
            start_secs = self._cumulative_secs
            self._cumulative_secs += duration_secs
            sf.write(str(saved_path), audio_array, self._actual_samplerate)
            duration_min = duration_secs / 60
            saved_name = saved_path.name
            self._part_index += 1
            self._part_start = _time_mod.monotonic()
            self._part_paused_duration = 0.0
            self.current_file = self._wav_dir_ref / f"{self._base_timestamp}_part{self._part_index:02d}.wav"
            self._notify_queue.append(
                f"파트 {self._part_index - 1} 저장 완료 ({duration_min:.1f}분) — "
                f"파트 {self._part_index} 녹음 중... ({saved_name})"
            )
            self._pending_transcriptions.append({
                "wav_path": str(saved_path),
                "part_index": current_part,
                "start_sec": start_secs,
                "end_sec": self._cumulative_secs,
                "has_parts": True,
            })
        self._schedule_chunk_timer()

    def pop_chunk_message(self) -> str | None:
        """저장된 청크 알림 메시지를 꺼낸다. 없으면 None."""
        return self._notify_queue.popleft() if self._notify_queue else None

    def pop_pending_transcription(self) -> dict | None:
        """전사 대기 작업을 꺼낸다. 없으면 None."""
        return self._pending_transcriptions.popleft() if self._pending_transcriptions else None

    def pause(self) -> str:
        """녹음 일시정지."""
        if not self.recording:
            return "녹음 중이 아닙니다."
        if self.paused:
            return "이미 일시정지 중입니다."
        self.paused = True
        self._pause_start = _time_mod.monotonic()
        return "일시정지됨 — 재개하려면 ▶ 재개 버튼을 누르세요"

    def resume(self) -> str:
        """녹음 재개."""
        if not self.recording:
            return "녹음 중이 아닙니다."
        if not self.paused:
            return "일시정지 상태가 아닙니다."
        self.paused = False
        if self._pause_start:
            elapsed = _time_mod.monotonic() - self._pause_start
            self._paused_duration += elapsed
            self._part_paused_duration += elapsed
            self._pause_start = None
        return "녹음 재개됨"

    def stop(self) -> tuple[str | None, str]:
        """녹음 종료 후 WAV 저장."""
        if not self.recording:
            return None, "녹음 중이 아닙니다."

        self.recording = False
        self.paused = False
        self._recording_start = None
        self._part_start = None
        self._pause_start = None

        if self._chunk_timer:
            self._chunk_timer.cancel()
            self._chunk_timer = None

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if self._wasapi_thread:
            self._wasapi_thread.join(timeout=2)
            self._wasapi_thread = None

        if self._mix_thread:
            self._mix_thread.join(timeout=2)
            self._mix_thread = None

        with self.lock:
            mic_data = list(self.audio_data)
            mix_data = list(self._mix_audio_data)

        if self._is_mixed:
            self._is_mixed = False
            self._mix_audio_data = []
            if not mic_data and not mix_data:
                return None, "녹음된 데이터가 없습니다."
            mic_arr = np.concatenate(mic_data, axis=0) if mic_data else None
            mix_arr = np.concatenate(mix_data, axis=0) if mix_data else None
            if mic_arr is not None and mix_arr is not None:
                min_len = min(len(mic_arr), len(mix_arr))
                audio_array = np.clip(mic_arr[:min_len] + mix_arr[:min_len], -1.0, 1.0)
            else:
                audio_array = mic_arr if mic_arr is not None else mix_arr
        else:
            if not mic_data:
                return None, "녹음된 데이터가 없습니다."
            audio_array = np.concatenate(mic_data, axis=0)

        sf.write(str(self.current_file), audio_array, self._actual_samplerate)
        duration = len(audio_array) / self._actual_samplerate
        start_secs = self._cumulative_secs
        self._cumulative_secs += duration
        self._pending_transcriptions.append({
            "wav_path": str(self.current_file),
            "part_index": self._part_index,
            "start_sec": start_secs,
            "end_sec": self._cumulative_secs,
            "has_parts": self._chunk_seconds > 0,
        })
        part_info = f" (파트 {self._part_index})" if self._chunk_seconds > 0 else ""
        return str(self.current_file), f"녹음 완료{part_info}: {duration:.1f}초 ({self.current_file.name})"

    # ------------------------------------------------------------------
    # 장치 목록 조회
    # ------------------------------------------------------------------

    def list_devices(self) -> str:
        """입력 가능한 오디오 장치 목록을 문자열로 반환 (호스트 API 정보 포함)."""
        apis = {i: api["name"] for i, api in enumerate(sd.query_hostapis())}
        lines = []
        for i, dev in enumerate(sd.query_devices()):
            ch = dev["max_input_channels"]
            name = dev["name"]
            is_rdp = is_rdp_device_name(name)
            is_lb = is_loopback_device_name(name)
            if ch <= 0 and not is_rdp and not is_lb:
                continue
            api_name = apis.get(dev.get("hostapi", 0), "?")
            tag = " [원격]" if is_rdp else (" [루프백]" if is_lb else "")
            ch_str = f"ch:{ch}" if ch > 0 else "ch:0 ⚠"
            lines.append(f"[{i}] {name}{tag} ({api_name}, {ch_str}, SR:{int(dev['default_samplerate'])}Hz)")
        return "\n".join(lines) if lines else "입력 장치 없음"
