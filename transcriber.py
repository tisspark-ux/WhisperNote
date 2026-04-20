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
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
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

    def _load_model(self):
        if self._model is None:
            # faster_whisper 직접 사용 — whisperx.load_model()은 pyannote VAD 필요
            self._model = WhisperModel(
                WHISPER_MODEL,
                device=self.device,
                compute_type=self.compute_type,
                download_root=str(Path(__file__).parent / "models"),
            )

    # ------------------------------------------------------------------
    # 전사
    # ------------------------------------------------------------------

    def transcribe(
        self,
        audio_path: str,
        on_progress: Callable[[str], None] | None = None,
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
            if on_progress:
                on_progress(msg)

        _progress("Whisper 모델 로딩 중...")
        self._load_model()

        _progress("오디오 전사 중...")
        # faster_whisper: 파일 경로 직접 전달, generator 반환
        fw_segments, _ = self._model.transcribe(
            audio_path,
            language=WHISPER_LANGUAGE,
            beam_size=5,
            vad_filter=False,
        )
        segments = [
            {"start": s.start, "end": s.end, "text": s.text}
            for s in fw_segments
        ]

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
        except Exception:
            pass

        # 화자 분리(Diarization) — resemblyzer 기반, 완전 오프라인
        diarization_ok = False
        if ENABLE_DIARIZATION and segments:
            try:
                _progress("화자 분리 중...")
                import diarizer
                segments = diarizer.diarize(audio_path, segments, num_speakers=NUM_SPEAKERS)
                diarization_ok = True
            except Exception as exc:
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
        stem = Path(audio_path).stem
        output_file = OUTPUTS_DIR / f"{stem}_transcript.txt"
        output_file.write_text(transcript, encoding="utf-8")

        _progress(f"전사 완료: {output_file.name}")
        return transcript, str(output_file)
