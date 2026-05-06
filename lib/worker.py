"""worker.py — 백그라운드 자동 전사/교정/요약 워커."""
import queue
import threading
from collections import deque
from pathlib import Path

from lib.instances import transcriber, summarizer


def _fmt_sec(secs: float) -> str:
    s = max(0, int(secs))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class AutoTranscriptionWorker:
    """녹음 청크 완료 시 순차 전사 → 전체 완료 후 자동 교정 + 요약."""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._results: deque = deque()
        self._thread: threading.Thread | None = None
        self._combined_path: Path | None = None
        self._out_dir: Path | None = None
        self._model_name: str | None = None
        self._summary_type: str = "회의"
        self._num_speakers: int | None = None
        self._lock = threading.Lock()
        self._current_label: str | None = None
        self._pending_labels: list = []
        self._session_active: bool = False
        self._finalize_triggered: bool = False
        self._corrected_path: Path | None = None
        self._progress_msg: str = ""
        self._part_audio_map: dict[int, str] = {}

    # ── 세션 초기화 ──────────────────────────────────────────
    def reset(self, combined_path: Path | None, out_dir: Path | None,
              model_name: str | None = None, summary_type: str = "회의",
              num_speakers: int | None = None):
        self._combined_path = combined_path
        self._out_dir = out_dir
        self._model_name = model_name
        self._summary_type = summary_type
        self._num_speakers = num_speakers
        self._corrected_path = None
        with self._lock:
            self._current_label = None
            self._pending_labels = []
            self._session_active = True
            self._finalize_triggered = False
            self._progress_msg = ""
            self._part_audio_map = {}

    # ── 대기열 관리 ──────────────────────────────────────────
    def _make_label(self, job: dict) -> str:
        if job.get("type") == "finalize":
            return "자동 교정 + 요약"
        part = job["part_index"]
        start = _fmt_sec(job["start_sec"])
        end = _fmt_sec(job["end_sec"])
        if job.get("has_parts"):
            return f"파트 {part} 전사 ({start} ~ {end})"
        return f"전사 ({start} ~ {end})"

    def enqueue(self, job: dict):
        label = self._make_label(job)
        with self._lock:
            self._pending_labels.append(label)
        self._queue.put(job)
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def enqueue_finalize(self):
        """모든 전사 완료 후 자동 교정 job 삽입."""
        with self._lock:
            self._finalize_triggered = True
        self.enqueue({"type": "finalize"})

    def enqueue_file(self, path: str):
        """외부 파일(업로드/폴더)을 전사 큐에 투입."""
        try:
            import soundfile as _sf
            info = _sf.info(path)
            duration = info.duration
        except Exception:
            duration = 0.0
        part = (
            len([j for j in list(self._queue.queue) if j.get("type") != "finalize"])
            + (1 if self._current_label else 0)
            + 1
        )
        job = {
            "wav_path": path,
            "part_index": part,
            "start_sec": 0.0,
            "end_sec": duration,
            "has_parts": True,
        }
        self.enqueue(job)

    def get_part_audio_map(self) -> dict:
        with self._lock:
            return dict(self._part_audio_map)

    def pop_result(self) -> dict | None:
        with self._lock:
            return self._results.popleft() if self._results else None

    def is_busy(self) -> bool:
        return not self._queue.empty() or (
            self._thread is not None and self._thread.is_alive()
        )

    def get_progress_msg(self) -> str:
        with self._lock:
            return self._progress_msg

    def _set_progress(self, pct: float, msg: str):
        with self._lock:
            self._progress_msg = msg

    def get_status_text(self) -> str:
        with self._lock:
            current = self._current_label
            pending = list(self._pending_labels)
        if not current and not pending:
            return ""
        lines = []
        if current:
            lines.append(f"🔄 처리 중: {current}")
        for p in pending:
            lines.append(f"⏳ 대기 중: {p}")
        return "\n".join(lines)

    # ── 백그라운드 실행 ──────────────────────────────────────
    def _run(self):
        while True:
            try:
                job = self._queue.get(timeout=2)
            except queue.Empty:
                break
            label = self._make_label(job)
            with self._lock:
                self._current_label = label
                if label in self._pending_labels:
                    self._pending_labels.remove(label)
            try:
                if job.get("type") == "finalize":
                    self._do_correct()
                    self._do_summarize()
                else:
                    self._do_transcribe(job)
            except Exception as exc:
                with self._lock:
                    self._results.append({"error": str(exc)})
            finally:
                with self._lock:
                    self._current_label = None
                    self._progress_msg = ""
                self._queue.task_done()

    def _do_transcribe(self, job: dict):
        wav_path   = job["wav_path"]
        part_index = job["part_index"]
        start_sec  = job["start_sec"]
        end_sec    = job["end_sec"]
        has_parts  = job["has_parts"]

        transcript_text, part_file = transcriber.transcribe(
            wav_path, output_dir=self._out_dir, num_speakers=self._num_speakers,
            on_progress=self._set_progress,
        )

        if has_parts:
            with self._lock:
                self._part_audio_map[part_index] = wav_path
            header = (
                f"[파트 {part_index} - "
                f"{_fmt_sec(start_sec)} ~ {_fmt_sec(end_sec)}]\n"
            )
            combined = self._combined_path
            if combined is not None:
                existing = combined.read_text(encoding="utf-8") if combined.exists() else ""
                sep = "\n\n" if existing else ""
                combined.write_text(
                    existing + sep + header + transcript_text, encoding="utf-8"
                )
                display_text  = combined.read_text(encoding="utf-8")
                status_msg    = f"파트 {part_index} 자동 전사 완료 — {combined.name}"
                file_path_str = str(combined)
            else:
                display_text  = header + transcript_text
                status_msg    = f"파트 {part_index} 자동 전사 완료 — {Path(part_file).name}"
                file_path_str = str(part_file)
        else:
            combined = self._combined_path
            if combined is not None:
                combined.write_text(transcript_text, encoding="utf-8")
                display_text  = transcript_text
                status_msg    = f"자동 전사 완료 — {combined.name}"
                file_path_str = str(combined)
            else:
                display_text  = transcript_text
                status_msg    = f"자동 전사 완료 — {Path(part_file).name}"
                file_path_str = str(part_file)

        with self._lock:
            self._results.append({
                "type": "transcript",
                "transcript": display_text,
                "file_path": file_path_str,
                "status": status_msg,
            })

    def _do_correct(self):
        combined = self._combined_path
        if combined is None or not combined.exists():
            return
        transcript_text = combined.read_text(encoding="utf-8").strip()
        if not transcript_text:
            return
        audio_stem = combined.stem.replace("_transcript", "")
        with self._lock:
            self._progress_msg = "교정 중..."
        try:
            corrected, c_file = summarizer.correct_transcript(
                transcript_text,
                audio_stem,
                model=self._model_name,
                output_dir=self._out_dir,
            )
            self._corrected_path = Path(c_file)
            with self._lock:
                self._results.append({
                    "type": "correction",
                    "correction": corrected,
                    "file_path": c_file,
                    "status": f"자동 교정 완료 — {Path(c_file).name}",
                })
        except Exception as exc:
            with self._lock:
                self._results.append({"error": f"자동 교정 실패: {exc}"})

    def _do_summarize(self):
        source = (
            self._corrected_path
            if self._corrected_path and self._corrected_path.exists()
            else self._combined_path
        )
        if source is None or not source.exists():
            return
        transcript_text = source.read_text(encoding="utf-8").strip()
        if not transcript_text:
            return
        audio_stem = source.stem.replace("_transcript_corrected", "").replace("_transcript", "")
        with self._lock:
            self._progress_msg = "요약 중..."
        try:
            summary, s_file = summarizer.summarize(
                transcript_text, audio_stem,
                model=self._model_name,
                output_dir=self._out_dir,
                summary_type=self._summary_type,
            )
            with self._lock:
                self._results.append({
                    "type": "summary",
                    "summary": summary,
                    "file_path": s_file,
                    "status": f"자동 요약 완료 — {Path(s_file).name}",
                })
        except Exception as exc:
            with self._lock:
                self._results.append({"error": f"자동 요약 실패: {exc}"})


auto_worker = AutoTranscriptionWorker()
