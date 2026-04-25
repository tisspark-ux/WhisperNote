from pathlib import Path

import requests

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OUTPUTS_DIR,
)
from prompts import get_correction_prompt, get_summary_prompt

OUTPUTS_DIR.mkdir(exist_ok=True)


class Summarizer:
    def __init__(self, model: str | None = None):
        self.model = model or OLLAMA_MODEL
        self.base_url = OLLAMA_BASE_URL

    # ------------------------------------------------------------------
    # Ollama 모델 목록
    # ------------------------------------------------------------------

    def get_available_models(self) -> list[str]:
        """Ollama 서버에서 사용 가능한 모델 목록을 반환."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return [m["name"] for m in models]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # 내부 Ollama 호출 헬퍼
    # ------------------------------------------------------------------

    def _call_ollama(self, model: str, prompt: str) -> str:
        """Ollama /api/generate 를 호출하고 응답 텍스트를 반환."""
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()

        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Ollama 서버({self.base_url})에 연결할 수 없습니다.\n"
                "터미널에서 `ollama serve` 를 실행한 뒤 다시 시도하세요."
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(
                f"Ollama 응답 시간 초과 ({OLLAMA_TIMEOUT}초).\n"
                "config.py 의 OLLAMA_TIMEOUT 을 늘리거나 더 빠른 모델을 사용하세요."
            )
        except requests.exceptions.HTTPError as exc:
            body = exc.response.text if exc.response is not None else "no response"
            code = exc.response.status_code if exc.response is not None else "?"
            raise RuntimeError(f"Ollama HTTP 오류: {code} – {body}")
        except Exception as exc:
            raise RuntimeError(f"Ollama 호출 실패: {exc}")

    # ------------------------------------------------------------------
    # 요약
    # ------------------------------------------------------------------

    def summarize(
        self,
        transcript: str,
        audio_stem: str,
        model: str | None = None,
        output_dir=None,
        summary_type: str = "회의",
    ) -> tuple[str, str]:
        """Ollama 로 전사문을 요약한다.

        Returns
        -------
        summary : str
        output_file : str
        """
        model = model or self.model
        prompt = get_summary_prompt(summary_type).format(transcript=transcript)
        summary = self._call_ollama(model, prompt)

        out_dir = output_dir if output_dir is not None else OUTPUTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"{audio_stem}_summary.txt"
        try:
            output_file.write_text(summary, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"요약 파일 저장 실패 ({output_file}): {exc}") from exc

        return summary, str(output_file)

    # ------------------------------------------------------------------
    # 전사 교정
    # ------------------------------------------------------------------

    def correct_transcript(
        self,
        transcript: str,
        audio_stem: str,
        model: str | None = None,
        output_dir=None,
    ) -> tuple[str, str]:
        """Ollama 로 전사문을 교정한다. 구어체 다듬기, 추임새 제거 등."""
        model = model or self.model
        prompt = get_correction_prompt().format(transcript=transcript)
        corrected = self._call_ollama(model, prompt)

        out_dir = output_dir if output_dir is not None else OUTPUTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"{audio_stem}_transcript_corrected.txt"
        try:
            output_file.write_text(corrected, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"교정 파일 저장 실패 ({output_file}): {exc}") from exc

        return corrected, str(output_file)
