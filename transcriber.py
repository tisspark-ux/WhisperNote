from pathlib import Path
from typing import Callable

import torch
import whisperx

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
            self._model = whisperx.load_model(
                WHISPER_MODEL,
                self.device,
                compute_type=self.compute_type,
                language=WHISPER_LANGUAGE,
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

        _progress("WhisperX 모델 로딩 중...")
        self._load_model()

        _progress("오디오 전사 중...")
        audio = whisperx.load_audio(audio_path)
        result = self._model.transcribe(
            audio,
            batch_size=WHISPER_BATCH_SIZE,
            language=WHISPER_LANGUAGE,
        )

        # 정렬(Alignment) — 실패 시 원본 세그먼트 유지
        try:
            _progress("타임스탬프 정렬 중...")
            align_model, metadata = whisperx.load_align_model(
                language_code=WHISPER_LANGUAGE,
                device=self.device,
            )
            result = whisperx.align(
                result["segments"],
                align_model,
                metadata,
                audio,
                self.device,
                return_char_alignments=False,
            )
        except Exception:
            pass

        segments = result.get("segments", [])

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
