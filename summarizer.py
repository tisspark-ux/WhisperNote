from pathlib import Path

import requests

from config import (
    CORRECTION_PROMPT_TEMPLATE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OUTPUTS_DIR,
    SUMMARY_PROMPT_TEMPLATE,
)

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
    # 요약
    # ------------------------------------------------------------------

    def summarize(
        self,
        transcript: str,
        audio_stem: str,
        model: str | None = None,
        output_dir=None,
    ) -> tuple[str, str]:
        """
        Ollama 로 전사문을 요약한다.

        Returns
        -------
        summary : str
            요약 텍스트
        output_file : str
            저장된 TXT 파일 경로
        """
        model = model or self.model
        prompt = SUMMARY_PROMPT_TEMPLATE.format(transcript=transcript)

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            summary = resp.json().get("response", "").strip()

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
            raise RuntimeError(f"Ollama 요약 실패: {exc}")

        # TXT 저장
        out_dir = output_dir if output_dir is not None else OUTPUTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"{audio_stem}_summary.txt"
        output_file.write_text(summary, encoding="utf-8")

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
        prompt = CORRECTION_PROMPT_TEMPLATE.format(transcript=transcript)

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            corrected = resp.json().get("response", "").strip()

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
            raise RuntimeError(f"Ollama 교정 실패: {exc}")

        out_dir = output_dir if output_dir is not None else OUTPUTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"{audio_stem}_transcript_corrected.txt"
        output_file.write_text(corrected, encoding="utf-8")

        return corrected, str(output_file)
