from pathlib import Path

import requests

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OUTPUTS_DIR,
)
from data.prompts import get_correction_prompt, get_summary_prompt

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

    def _call_ollama(self, model: str, prompt: str, num_ctx: int | None = None) -> str:
        """Ollama /api/generate 를 호출하고 응답 텍스트를 반환."""
        try:
            payload: dict = {"model": model, "prompt": prompt, "stream": False}
            if num_ctx is not None:
                payload["options"] = {"num_ctx": num_ctx}
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
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

    # 한국어 기준 글자당 약 1.5 토큰 (보수적 추정)
    _CHARS_PER_TOKEN = 1.5
    # 요약 출력 예비 토큰 (면담 요약은 내용이 길 수 있음)
    _SUMMARY_OUTPUT_RESERVE = 12_288
    # 요약 num_ctx 상한 (A4000 16GB VRAM 안전 범위)
    _SUMMARY_MAX_CTX = 131_072

    def _calc_num_ctx(self, text_chars: int) -> int:
        """전사문 길이로 num_ctx를 동적 산출 (2의 거듭제곱으로 올림)."""
        estimated = int(text_chars / self._CHARS_PER_TOKEN) + self._SUMMARY_OUTPUT_RESERVE
        ctx = 16_384
        while ctx < estimated:
            ctx <<= 1
        return min(ctx, self._SUMMARY_MAX_CTX)

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
        num_ctx = self._calc_num_ctx(len(transcript))
        print(
            f"[요약] num_ctx={num_ctx}, {len(transcript)}자, 유형={summary_type}...",
            flush=True,
        )
        prompt = get_summary_prompt(summary_type).format(transcript=transcript)
        summary = self._call_ollama(model, prompt, num_ctx=num_ctx)

        out_dir = output_dir if output_dir is not None else OUTPUTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"{audio_stem}_summary.txt"
        try:
            output_file.write_text(summary, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"요약 파일 저장 실패 ({output_file}): {exc}") from exc

        return summary, str(output_file)

    # ------------------------------------------------------------------
    # 교정 내부 헬퍼
    # ------------------------------------------------------------------
    # 직접 교정 가능한 최대 문자 수 (A4000 16GB, num_ctx=32768 기준)
    _DIRECT_CORRECT_MAX_CHARS = 20_000
    # 청크당 최대 문자 수
    _CHUNK_MAX_CHARS = 10_000
    # 직접 교정 시 num_ctx
    _DIRECT_NUM_CTX = 32_768
    # 청크 교정 시 num_ctx
    _CHUNK_NUM_CTX = 16_384

    _ECHO_ARTIFACTS = {"---", "전사문:", "교정:", "수정본:", "교정본:"}

    def _strip_prompt_echo(self, text: str) -> str:
        """LLM이 프롬프트 구분자를 응답 첫 줄에 에코할 때 제거."""
        lines = text.splitlines()
        while lines and lines[0].strip() in self._ECHO_ARTIFACTS:
            lines.pop(0)
        return "\n".join(lines)

    def _correct_in_chunks(self, model: str, transcript: str) -> str:
        """전사문을 ~6000자 청크 단위로 나누어 교정 후 합친다."""
        lines = transcript.splitlines(keepends=True)
        chunks: list[str] = []
        buf: list[str] = []
        buf_chars = 0

        for line in lines:
            buf.append(line)
            buf_chars += len(line)
            if buf_chars >= self._CHUNK_MAX_CHARS:
                chunks.append("".join(buf))
                buf, buf_chars = [], 0

        if buf:
            chunks.append("".join(buf))

        total = len(chunks)
        corrected_parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            print(f"[교정] 청크 {i}/{total} 교정 중...", flush=True)
            prompt = get_correction_prompt().format(transcript=chunk.rstrip("\n"))
            result = self._strip_prompt_echo(
                self._call_ollama(model, prompt, num_ctx=self._CHUNK_NUM_CTX)
            )
            corrected_parts.append(result)

        return "\n".join(corrected_parts)

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
        """Ollama 로 전사문을 교정한다. 구어체 다듬기, 추임새 제거 등.

        전사문 길이에 따라 자동 전환:
          - 10,000자 이하 → num_ctx=16384 로 직접 교정
          - 초과         → 6,000자 청크 단위로 나누어 순차 교정
        """
        model = model or self.model

        if len(transcript) <= self._DIRECT_CORRECT_MAX_CHARS:
            print(
                f"[교정] 직접 교정 (num_ctx={self._DIRECT_NUM_CTX}, "
                f"{len(transcript)}자)...",
                flush=True,
            )
            prompt = get_correction_prompt().format(transcript=transcript)
            corrected = self._strip_prompt_echo(
                self._call_ollama(model, prompt, num_ctx=self._DIRECT_NUM_CTX)
            )
        else:
            print(
                f"[교정] 청크 교정 (num_ctx={self._CHUNK_NUM_CTX}, "
                f"{len(transcript)}자, 청크~{self._CHUNK_MAX_CHARS}자)...",
                flush=True,
            )
            corrected = self._correct_in_chunks(model, transcript)

        out_dir = output_dir if output_dir is not None else OUTPUTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"{audio_stem}_transcript_corrected.txt"
        try:
            output_file.write_text(corrected, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"교정 파일 저장 실패 ({output_file}): {exc}") from exc

        return corrected, str(output_file)
