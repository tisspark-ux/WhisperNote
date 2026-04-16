from pathlib import Path
from typing import Callable

import torch
import whisperx

from config import (
    ENABLE_DIARIZATION,
    HF_TOKEN,
    MAX_SPEAKERS,
    MIN_SPEAKERS,
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
        self._diarize_model = None
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

    def _load_diarize_model(self):
        if self._diarize_model is None:
            if not HF_TOKEN:
                raise RuntimeError(
                    "화자 분리를 사용하려면 config.py 의 HF_TOKEN 을 설정해야 합니다.\n"
                    "1. https://huggingface.co/settings/tokens 에서 토큰 발급\n"
                    "2. https://hf.co/pyannote/speaker-diarization-3.1 약관 동의\n"
                    "3. https://hf.co/pyannote/segmentation-3.0 약관 동의"
                )
            self._diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=HF_TOKEN,
                device=self.device,
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

        # 정렬(Alignment) — 화자 분리의 단어 단위 매핑에 필요, 실패 시 원본 유지
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

        # 화자 분리(Diarization)
        diarization_ok = False
        if ENABLE_DIARIZATION:
            try:
                _progress("화자 분리 모델 로딩 중...")
                self._load_diarize_model()

                _progress("화자 분리 실행 중...")
                kwargs: dict = {}
                if MIN_SPEAKERS is not None:
                    kwargs["min_speakers"] = MIN_SPEAKERS
                if MAX_SPEAKERS is not None:
                    kwargs["max_speakers"] = MAX_SPEAKERS

                diarize_segments = self._diarize_model(audio, **kwargs)
                result = whisperx.assign_word_speakers(diarize_segments, result)
                diarization_ok = True
            except RuntimeError:
                raise   # HF_TOKEN 미설정 등 명시적 오류는 그대로 전파
            except Exception as exc:
                # 그 외 오류(네트워크 등)는 화자 분리 없이 계속
                _progress(f"화자 분리 실패 (전사만 저장): {exc}")

        # 세그먼트 → 텍스트 변환
        segments = result.get("segments", [])
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
