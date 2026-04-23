from pathlib import Path
from typing import Callable
from math import gcd

import numpy as np
import torch
import whisperx
from faster_whisper import WhisperModel

from config import (
    ENABLE_DIARIZATION,
    NUM_SPEAKERS,
    OUTPUTS_DIR,
    WHISPER_BATCH_SIZE,
    WHISPER_BEAM_SIZE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_INITIAL_PROMPT,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
    WHISPER_VAD_FILTER,
)

OUTPUTS_DIR.mkdir(exist_ok=True)

SAMPLE_RATE = 16000


def _load_audio(file: str, sr: int = SAMPLE_RATE) -> np.ndarray:
    """ffmpeg 바이너리 없이 오디오 로드 (soundfile → PyAV fallback).
    WAV/FLAC/OGG: soundfile 직접 처리
    MP3/M4A 등: PyAV(ffmpeg 라이브러리 번들) 사용
    """
    import soundfile as sf
    try:
        audio, orig_sr = sf.read(file, dtype="float32", always_2d=True)
        audio = audio.mean(axis=1)
        if orig_sr != sr:
            from scipy.signal import resample_poly
            g = gcd(int(orig_sr), sr)
            audio = resample_poly(audio, sr // g, int(orig_sr) // g).astype(np.float32)
        return audio
    except Exception:
        pass

    import av
    container = av.open(file)
    stream = next((s for s in container.streams if s.type == "audio"), None)
    if stream is None:
        raise RuntimeError(f"오디오 스트림을 찾을 수 없습니다: {file}")
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=sr)
    chunks: list[np.ndarray] = []
    for frame in container.decode(stream):
        frame.pts = None
        for rf in resampler.resample(frame):
            chunks.append(rf.to_ndarray()[0])
    for rf in resampler.resample(None):
        chunks.append(rf.to_ndarray()[0])
    return np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(0, dtype=np.float32)


# whisperX의 load_audio를 ffmpeg 바이너리 없이 동작하는 버전으로 교체
whisperx.load_audio = _load_audio


class Transcriber:
    def __init__(self):
        self._model = None
        # GPU가 없으면 CPU + int8 로 자동 전환
        self.device = WHISPER_DEVICE if torch.cuda.is_available() else "cpu"
        self.compute_type = WHISPER_COMPUTE_TYPE if self.device == "cuda" else "int8"

    # ------------------------------------------------------------------
    # 모델 로드 (최초 1회만 실행)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_model_cached() -> bool:
        """faster-whisper 모델이 로컬 캐시에 있는지 확인."""
        models_dir = Path(__file__).parent / "models"
        return any(models_dir.rglob("model.bin")) or any(models_dir.rglob("model.safetensors"))

    def _load_model(self):
        if self._model is None:
            gpu_info = ""
            if self.device == "cuda":
                try:
                    gpu_info = f" [{torch.cuda.get_device_name(0)}]"
                except Exception:
                    pass
            else:
                gpu_info = " (GPU 없음 → CPU 사용, 속도 느림)"

            print(f"[전사] 모델 로딩 중: {WHISPER_MODEL} / {self.device}{gpu_info} / {self.compute_type}", flush=True)

            if not self._is_model_cached():
                _SIZE = {
                    "tiny": "75MB", "base": "145MB", "small": "466MB",
                    "medium": "1.5GB", "large-v3": "3.1GB", "large-v3-turbo": "1.6GB",
                }
                size_hint = _SIZE.get(WHISPER_MODEL, "~수백MB")
                print(f"[다운로드] {WHISPER_MODEL} 모델 없음 — HuggingFace 다운로드 시작 (예상 크기: {size_hint})", flush=True)
                print("[다운로드] 아래에 진행 상황이 표시됩니다...", flush=True)
                self._model = self._load_with_progress()
            else:
                self._model = WhisperModel(
                    WHISPER_MODEL,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=str(Path(__file__).parent / "models"),
                )

            print("[전사] 모델 로딩 완료", flush=True)

    def _load_with_progress(self) -> "WhisperModel":
        """tqdm을 교체해 [다운로드] 형식으로 진행률 출력 후 모델 로드."""
        import tqdm as _tqdm_mod

        _orig_tqdm = _tqdm_mod.tqdm

        class _DownloadTqdm(_orig_tqdm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._last_pct = -1

            def update(self, n=1):
                super().update(n)
                if self.total and self.total > 1024 * 1024:
                    pct = int(self.n / self.total * 100)
                    if pct != self._last_pct and pct % 5 == 0:
                        mb_done  = self.n / (1024 ** 2)
                        mb_total = self.total / (1024 ** 2)
                        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                        desc = getattr(self, "desc", "") or ""
                        print(
                            f"\r[다운로드] {bar} {pct:3d}%  {mb_done:.0f}/{mb_total:.0f}MB  {desc}",
                            end="", flush=True,
                        )
                        self._last_pct = pct
                        if pct == 100:
                            print(flush=True)

        _tqdm_mod.tqdm = _DownloadTqdm
        try:
            model = WhisperModel(
                WHISPER_MODEL,
                device=self.device,
                compute_type=self.compute_type,
                download_root=str(Path(__file__).parent / "models"),
            )
        finally:
            _tqdm_mod.tqdm = _orig_tqdm
        return model

    # ------------------------------------------------------------------
    # 전사
    # ------------------------------------------------------------------

    def transcribe(
        self,
        audio_path: str,
        on_progress: Callable[[str], None] | None = None,
        output_dir=None,
    ) -> tuple[str, str]:
        """
        WhisperX 로 오디오 파일을 전사한다.
        ENABLE_DIARIZATION=True 이면 화자 분리까지 수행한다.

        Returns
        -------
        transcript : str
            타임스탬프 + (화자 레이블)이 포함된 전사 텍스트
        output_file : str
            저장된 TXT 파일 경로
        """
        def _progress(msg: str):
            print(f"[전사] {msg}", flush=True)
            if on_progress:
                on_progress(msg)

        print(f"[전사] 시작: {Path(audio_path).name}", flush=True)

        _progress("Whisper 모델 로딩 중...")
        self._load_model()

        _progress("오디오 전사 중... (파일 크기/CPU 성능에 따라 수 분~수십 분 소요)")
        # faster_whisper: 파일 경로 직접 전달, generator 반환
        fw_segments, fw_info = self._model.transcribe(
            audio_path,
            language=WHISPER_LANGUAGE,
            beam_size=WHISPER_BEAM_SIZE,
            vad_filter=WHISPER_VAD_FILTER,
            initial_prompt=WHISPER_INITIAL_PROMPT,
            temperature=0,
            condition_on_previous_text=True,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
        )
        print(f"[전사] 오디오 길이: {fw_info.duration:.1f}초, 감지 언어: {fw_info.language} (신뢰도 {fw_info.language_probability:.0%})", flush=True)

        segments = []
        for i, s in enumerate(fw_segments):
            segments.append({"start": s.start, "end": s.end, "text": s.text})
            if i % 20 == 0 and i > 0:
                print(f"[전사] 세그먼트 {i}개 처리 중... ({s.end:.0f}s / {fw_info.duration:.0f}s)", flush=True)

        print(f"[전사] 세그먼트 {len(segments)}개 완료", flush=True)

        # 정렬(Alignment) — 실패 시 원본 세그먼트 유지
        try:
            _progress("타임스탬프 정렬 중...")
            audio = whisperx.load_audio(audio_path)
            align_model, metadata = whisperx.load_align_model(
                language_code=WHISPER_LANGUAGE,
                device=self.device,
            )
            aligned = whisperx.align(
                segments,
                align_model,
                metadata,
                audio,
                self.device,
                return_char_alignments=False,
            )
            segments = aligned.get("segments", segments)
            print("[전사] 타임스탬프 정렬 완료", flush=True)
        except Exception as exc:
            print(f"[전사] 타임스탬프 정렬 생략 (오류: {exc})", flush=True)

        # 화자 분리(Diarization) — resemblyzer 기반, 완전 오프라인
        diarization_ok = False
        if ENABLE_DIARIZATION and segments:
            try:
                _progress("화자 분리 중...")
                import diarizer
                segments = diarizer.diarize(audio_path, segments, num_speakers=NUM_SPEAKERS)
                diarization_ok = True
                print("[전사] 화자 분리 완료", flush=True)
            except Exception as exc:
                print(f"[전사] 화자 분리 실패: {exc}", flush=True)
                _progress(f"화자 분리 실패 (전사만 저장): {exc}")

        # 세그먼트 → 텍스트 변환
        lines: list[str] = []
        for seg in segments:
            start   = seg.get("start", 0.0)
            end     = seg.get("end",   0.0)
            text    = seg.get("text",  "").strip()
            speaker = seg.get("speaker", "")

            if not text:
                continue

            if diarization_ok and speaker:
                lines.append(f"[{speaker}] [{start:.1f}s - {end:.1f}s] {text}")
            else:
                lines.append(f"[{start:.1f}s - {end:.1f}s] {text}")

        transcript = "\n".join(lines)

        # TXT 저장
        out_dir = output_dir if output_dir is not None else OUTPUTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(audio_path).stem
        output_file = out_dir / f"{stem}_transcript.txt"
        output_file.write_text(transcript, encoding="utf-8")

        print(f"[전사] 저장 완료: {output_file}", flush=True)
        _progress(f"전사 완료: {output_file.name}")
        return transcript, str(output_file)
