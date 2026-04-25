"""
WhisperNote – 회의 녹음 → 전사 → 요약 자동화
실행: python app.py
"""

import os
import sys
import logging
import traceback
import queue
import threading
from collections import deque
from pathlib import Path

# 에러 로그 — logs/ 폴더에 날짜별 파일로 수집
_LOGS_DIR = Path(__file__).parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)
_LOG_PATH = _LOGS_DIR / f"{__import__('datetime').date.today():%Y-%m-%d}.log"
logging.basicConfig(
    filename=str(_LOG_PATH),
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s: %(message)s",
    encoding="utf-8",
)

def _handle_exception(exc_type, exc_value, exc_tb):
    logging.error("미처리 예외", exc_info=(exc_type, exc_value, exc_tb))
    traceback.print_exception(exc_type, exc_value, exc_tb)

sys.excepthook = _handle_exception

# Windows CMD Quick Edit Mode 비활성화
# Quick Edit가 켜져 있으면 창을 클릭하는 순간 프로세스가 일시정지됨 (키 입력 시 재개)
if sys.platform == "win32":
    try:
        import ctypes as _ct
        _k32 = _ct.windll.kernel32
        _h = _k32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        _m = _ct.c_ulong()
        _k32.GetConsoleMode(_h, _ct.byref(_m))
        _k32.SetConsoleMode(_h, (_m.value & ~0x0040) | 0x0080)  # clear ENABLE_QUICK_EDIT
    except Exception:
        pass

# WhisperX 모델 캐시를 프로젝트 내 models/ 폴더로 지정 (HuggingFace 최초 다운 후 오프라인 동작)
os.environ.setdefault("HF_HOME", str(Path(__file__).parent / "models"))
os.environ.setdefault("TORCH_HOME", str(Path(__file__).parent / "models"))

# 회사 프록시에서 localhost 제외 (Gradio가 자기 서버에 연결할 수 있도록)
for _k in ("no_proxy", "NO_PROXY"):
    _cur = os.environ.get(_k, "")
    _add = "localhost,127.0.0.1,0.0.0.0"
    os.environ[_k] = f"{_cur},{_add}" if _cur else _add

# Windows: 127.0.0.1 을 시스템 프록시 예외 목록에 추가 (HKCU, 관리자 권한 불필요)
# → run.bat 에서 PowerShell/특수문자 없이 브라우저 프록시 우회 처리
if sys.platform == "win32":
    try:
        import winreg as _reg
        _IK = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        try:
            _rk = _reg.OpenKey(_reg.HKEY_CURRENT_USER, _IK, 0, _reg.KEY_ALL_ACCESS)
            _cur_bypass = _reg.QueryValueEx(_rk, "ProxyOverride")[0]
        except OSError:
            _rk = _reg.CreateKey(_reg.HKEY_CURRENT_USER, _IK)
            _cur_bypass = ""
        if "127.0.0.1" not in _cur_bypass:
            _new_bypass = (_cur_bypass + ";127.0.0.1;localhost") if _cur_bypass else "127.0.0.1;localhost"
            _reg.SetValueEx(_rk, "ProxyOverride", 0, _reg.REG_SZ, _new_bypass)
        _reg.CloseKey(_rk)
    except Exception:
        pass

print("WhisperNote 시작 중...", flush=True)
print("  [1/3] 네트워크 라이브러리 로딩...", flush=True)

# 회사 프록시 SSL 인증서 우회 (자체 서명 인증서 체인 오류 방지)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests as _req
_orig_req = _req.Session.request
def _no_ssl_verify(self, method, url, **kwargs):
    kwargs.setdefault("verify", False)
    # localhost는 프록시 없이 직접 연결 (회사 프록시 우회)
    if any(x in str(url) for x in ("localhost", "127.0.0.1", "0.0.0.0")):
        kwargs["proxies"] = {"http": None, "https": None}
    return _orig_req(self, method, url, **kwargs)
_req.Session.request = _no_ssl_verify

print("  [2/3] Gradio 로딩...", flush=True)
import gradio as gr

# Gradio 4.x bug: several gradio_client.utils functions crash when a JSON Schema
# value is True/False (valid per JSON Schema spec, meaning "any"/"never").
# Patch all three affected functions so none of them do 'in schema' on a bool.
try:
    import gradio_client.utils as _gcu

    if hasattr(_gcu, "_json_schema_to_python_type"):
        _orig_j2p = _gcu._json_schema_to_python_type
        def _j2p_patched(schema, defs=None):
            if isinstance(schema, bool):
                return "any"
            return _orig_j2p(schema, defs)
        _gcu._json_schema_to_python_type = _j2p_patched

    if hasattr(_gcu, "get_type"):
        _orig_get_type = _gcu.get_type
        def _get_type_patched(schema):
            if isinstance(schema, bool):
                return "any"
            return _orig_get_type(schema)
        _gcu.get_type = _get_type_patched

    if hasattr(_gcu, "get_desc"):
        _orig_get_desc = _gcu.get_desc
        def _get_desc_patched(schema):
            if isinstance(schema, bool):
                return ""
            return _orig_get_desc(schema)
        _gcu.get_desc = _get_desc_patched

except Exception:
    pass

# Gradio의 localhost 접근 가능 여부 체크 함수를 패치
# 회사 프록시가 localhost까지 차단하는 환경 대응
# (Gradio 버전마다 내부 API가 다를 수 있으므로 try/except 로 감쌈)
try:
    import gradio.networking as _gn
    if hasattr(_gn, "url_ok"):
        _orig_url_ok = _gn.url_ok
        def _url_ok_patched(url: str) -> bool:
            if any(x in url for x in ("localhost", "127.0.0.1", "0.0.0.0")):
                return True
            return _orig_url_ok(url)
        _gn.url_ok = _url_ok_patched
except Exception:
    pass

print("  [3/3] AI 라이브러리 로딩 중 (최초 실행 시 30초 이상 소요)...", flush=True)
from version import __version__
from config import OLLAMA_MODEL
from recorder import AudioRecorder, is_loopback_device_name, is_rdp_device_name
from summarizer import Summarizer
from transcriber import Transcriber
import categories as cat_mod
import storage
import prompts

_LOOPBACK_AUTO = -2
_REMOTE_AUTO   = -3
_WASAPI_AUTO   = -4
_MIX_AUTO      = -5

print(f"WhisperNote v{__version__}")

# GPU 상태 출력 (전사 가능 여부 확인용)
try:
    import torch as _torch
    _torch_cuda_ver = getattr(_torch.version, "cuda", None)
    if _torch.cuda.is_available():
        _gpu = _torch.cuda.get_device_name(0)
        _mem = _torch.cuda.get_device_properties(0).total_memory // (1024**3)
        print(f"  GPU: {_gpu} ({_mem}GB) — CUDA {_torch_cuda_ver} 전사 사용 가능", flush=True)
    elif _torch_cuda_ver is None:
        print("  [경고] PyTorch CPU 전용 빌드가 설치되어 있습니다.", flush=True)
        print("         install.bat 을 재실행하면 CUDA 버전으로 재설치됩니다.", flush=True)
    else:
        print(f"  [경고] PyTorch CUDA {_torch_cuda_ver} 빌드이지만 GPU를 인식하지 못했습니다.", flush=True)
        print("         NVIDIA 드라이버가 설치되어 있는지 확인하세요 (nvidia-smi).", flush=True)
except Exception:
    print("  GPU 상태 확인 불가", flush=True)

recorder   = AudioRecorder()
transcriber = Transcriber()
summarizer  = Summarizer()


def _fmt_sec(secs: float) -> str:
    s = max(0, int(secs))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class AutoTranscriptionWorker:
    """녹음 청크 완료 시 순차 전사 → 전체 완료 후 자동 요약."""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._results: deque = deque()
        self._thread: threading.Thread | None = None
        self._combined_path: Path | None = None
        self._out_dir: Path | None = None
        self._model_name: str | None = None
        self._summary_type: str = "회의"
        self._lock = threading.Lock()
        self._current_label: str | None = None
        self._pending_labels: list = []
        self._session_active: bool = False
        self._finalize_triggered: bool = False
        self._corrected_path: Path | None = None

    # ── 세션 초기화 ──────────────────────────────────────────
    def reset(self, combined_path: Path | None, out_dir: Path | None,
              model_name: str | None = None, summary_type: str = "회의"):
        self._combined_path = combined_path
        self._out_dir = out_dir
        self._model_name = model_name
        self._summary_type = summary_type
        self._corrected_path = None
        with self._lock:
            self._current_label = None
            self._pending_labels = []
            self._session_active = True
            self._finalize_triggered = False

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
        part = len([j for j in list(self._queue.queue) if j.get("type") != "finalize"]) + (1 if self._current_label else 0) + 1
        job = {
            "wav_path": path,
            "part_index": part,
            "start_sec": 0.0,
            "end_sec": duration,
            "has_parts": True,
        }
        self.enqueue(job)

    def pop_result(self) -> dict | None:
        with self._lock:
            return self._results.popleft() if self._results else None

    def is_busy(self) -> bool:
        return not self._queue.empty() or (
            self._thread is not None and self._thread.is_alive()
        )

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
                self._queue.task_done()

    def _do_transcribe(self, job: dict):
        wav_path   = job["wav_path"]
        part_index = job["part_index"]
        start_sec  = job["start_sec"]
        end_sec    = job["end_sec"]
        has_parts  = job["has_parts"]

        transcript_text, part_file = transcriber.transcribe(
            wav_path, output_dir=self._out_dir
        )

        if has_parts:
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
                display_text = combined.read_text(encoding="utf-8")
                status_msg   = f"파트 {part_index} 자동 전사 완료 — {combined.name}"
                file_path_str = str(combined)
            else:
                display_text  = header + transcript_text
                status_msg    = f"파트 {part_index} 자동 전사 완료 — {Path(part_file).name}"
                file_path_str = str(part_file)
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
        source = (self._corrected_path if self._corrected_path and self._corrected_path.exists()
                  else self._combined_path)
        if source is None or not source.exists():
            return
        transcript_text = source.read_text(encoding="utf-8").strip()
        if not transcript_text:
            return
        audio_stem = source.stem.replace("_transcript_corrected", "").replace("_transcript", "")
        try:
            summary, s_file = summarizer.summarize(
                transcript_text, audio_stem, model=self._model_name,
                output_dir=self._out_dir, summary_type=self._summary_type,
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

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
/* ── 전체 배경 ── */
body, .gradio-container {
    background: #0f1117 !important;
    font-family: 'Inter', 'Pretendard', -apple-system, sans-serif !important;
}

/* ── 헤더 ── */
#wn-header {
    padding: 2.4rem 0 1.6rem;
    text-align: center;
    border-bottom: 1px solid #1e2130;
    margin-bottom: 1.6rem;
}
#wn-header h1 {
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #e8eaf6;
    margin: 0 0 0.4rem;
}
#wn-header p {
    color: #6b7280;
    font-size: 0.92rem;
    margin: 0;
}

/* ── 카드 ── */
.wn-card {
    background: #161b27 !important;
    border: 1px solid #1e2130 !important;
    border-radius: 12px !important;
    padding: 1.2rem 1.4rem !important;
}

/* ── 섹션 레이블 ── */
.wn-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #4b5563;
    margin-bottom: 0.6rem;
}

/* ── 상태 뱃지 ── */
#record-status textarea {
    background: #0d1117 !important;
    border: 1px solid #1e2130 !important;
    border-radius: 8px !important;
    color: #9ca3af !important;
    font-size: 0.85rem !important;
}

/* ── 버튼 – 녹음 시작 ── */
#btn-start {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    border-radius: 10px !important;
    color: #fff !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    height: 48px !important;
    transition: opacity .2s !important;
}
#btn-start:hover { opacity: .85 !important; }

/* ── 버튼 – 녹음 종료 ── */
#btn-stop {
    background: linear-gradient(135deg, #ef4444, #f97316) !important;
    border: none !important;
    border-radius: 10px !important;
    color: #fff !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    height: 48px !important;
    transition: opacity .2s !important;
}
#btn-stop:hover { opacity: .85 !important; }
#btn-stop:disabled { opacity: .35 !important; }

/* ── 버튼 – 파이프라인 ── */
#btn-pipeline {
    background: linear-gradient(135deg, #0ea5e9, #6366f1) !important;
    border: none !important;
    border-radius: 10px !important;
    color: #fff !important;
    font-weight: 600 !important;
    height: 48px !important;
    width: 100% !important;
    font-size: 1rem !important;
    margin-top: 0.4rem !important;
    transition: opacity .2s !important;
}
#btn-pipeline:hover { opacity: .85 !important; }

/* ── 버튼 – 보조 ── */
.wn-btn-secondary {
    background: #1e2130 !important;
    border: 1px solid #2d3348 !important;
    border-radius: 8px !important;
    color: #9ca3af !important;
    font-size: 0.85rem !important;
    height: 38px !important;
    transition: background .2s !important;
}
.wn-btn-secondary:hover { background: #252b40 !important; color: #e5e7eb !important; }

/* ── 텍스트 박스 (결과) ── */
.wn-result textarea {
    background: #0d1117 !important;
    border: 1px solid #1e2130 !important;
    border-radius: 10px !important;
    color: #d1d5db !important;
    font-size: 0.88rem !important;
    line-height: 1.7 !important;
    padding: 1rem !important;
}

/* ── 드롭다운 ── */
.wn-dropdown select, .wn-dropdown input {
    background: #0d1117 !important;
    border: 1px solid #1e2130 !important;
    border-radius: 8px !important;
    color: #d1d5db !important;
}

/* ── 파일 경로 ── */
.wn-filepath textarea {
    background: transparent !important;
    border: none !important;
    border-top: 1px solid #1e2130 !important;
    border-radius: 0 !important;
    color: #4b5563 !important;
    font-size: 0.78rem !important;
    font-family: 'JetBrains Mono', monospace !important;
    padding: 0.5rem 0 0 !important;
}

/* ── 구분선 ── */
.wn-divider {
    border: none;
    border-top: 1px solid #1e2130;
    margin: 1rem 0;
}

/* ── 탭 ── */
.tab-nav button {
    background: transparent !important;
    border: none !important;
    color: #6b7280 !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    padding: 0.6rem 1.2rem !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
}
.tab-nav button.selected {
    color: #818cf8 !important;
    border-bottom-color: #818cf8 !important;
}

/* ── 파이프라인 상태 ── */
#pipeline-status textarea {
    background: #0a0f1a !important;
    border: 1px solid #1e2130 !important;
    border-radius: 8px !important;
    color: #6ee7b7 !important;
    font-size: 0.85rem !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Upload 박스 ── */
.wn-upload {
    border: 1.5px dashed #2d3348 !important;
    border-radius: 10px !important;
    background: #0d1117 !important;
}
.wn-upload:hover { border-color: #6366f1 !important; }

/* ── 오디오 레벨 미터 ── */
.wn-level-bar {
    background: #0d1117 !important;
    border: 1px solid #2d3348 !important;
    border-radius: 6px !important;
    padding: 6px 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
    color: #6ee7b7 !important;
    letter-spacing: 2px;
}
.wn-level-idle { color: #4b5563 !important; letter-spacing: normal; }
/* 레벨 미터 컨테이너 높이 고정 — 0.2s 갱신 시 레이아웃 흔들림 방지 */
#wn-level-wrap { min-height: 36px !important; height: 36px !important; overflow: hidden !important; }
#wn-level-wrap > div { height: 36px !important; }

/* ── 분류 설정 패널 ── */
.wn-cat-panel { margin-bottom: 1rem !important; position: relative !important; }
#btn-cat-close { position: absolute !important; top: 0.6rem !important; right: 0.6rem !important; width: auto !important; min-width: 70px !important; }
.wn-cat-col { border-right: 1px solid #1e2130; padding-right: 0.6rem !important; min-height: 160px; }
.wn-cat-col:last-child { border-right: none !important; }
.wn-cat-col-header {
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: #818cf8;
    padding: 0.3rem 0; border-bottom: 1px solid #2d3348; margin-bottom: 0.4rem;
}
/* Radio 스타일 */
.wn-cat-radio fieldset { border: none !important; padding: 0 !important; margin: 0 !important; }
.wn-cat-radio input[type="radio"] { display: none !important; }
.wn-cat-radio label {
    display: flex !important; align-items: center !important;
    padding: 0.25rem 0.4rem !important; border-radius: 5px !important;
    color: #9ca3af !important; font-size: 0.86rem !important;
    cursor: pointer !important; transition: background .12s !important;
    gap: 0.4rem !important;
}
.wn-cat-radio label:hover { background: #1e2130 !important; }
.wn-cat-radio label:has(input:checked) { background: #1e2130 !important; color: #e8eaf6 !important; font-weight: 500 !important; }
.wn-cat-radio label:has(input:checked)::before { content: "▶"; color: #818cf8; font-size: 0.6rem; }
.wn-cat-radio label:not(:has(input:checked))::before { content: "  "; }
/* 분류 소형 버튼 */
.wn-cat-btn-sm {
    background: #161b27 !important; border: 1px solid #2d3348 !important;
    border-radius: 5px !important; color: #6b7280 !important;
    font-size: 0.78rem !important; height: 28px !important;
    padding: 0 0.5rem !important; min-width: 0 !important;
    transition: all .12s !important;
}
.wn-cat-btn-sm:hover { border-color: #818cf8 !important; color: #818cf8 !important; background: #1e2130 !important; }
.wn-cat-btn-del:hover { border-color: #ef4444 !important; color: #ef4444 !important; }
/* 경로 표시 */
.wn-cat-path { font-size: 0.76rem !important; font-family: 'JetBrains Mono', monospace !important; color: #4b5563 !important; padding: 0.25rem 0 !important; }
.wn-cat-path-active { color: #818cf8 !important; }
/* 설정 버튼 */
#btn-cat-settings { background: #161b27 !important; border: 1px solid #2d3348 !important; border-radius: 8px !important; color: #6b7280 !important; height: 36px !important; min-width: 36px !important; }
#btn-cat-settings:hover { border-color: #818cf8 !important; color: #818cf8 !important; }

/* ── 전사 결과 헤더 행: 라벨 좌측, 라디오 우측 ── */
.wn-view-row { display: flex !important; align-items: center !important; justify-content: space-between !important; }
.wn-view-row > * { flex: 0 0 auto !important; }
.wn-view-radio { width: auto !important; }
.wn-view-radio fieldset { display: flex !important; flex-direction: row !important; gap: 0.5rem !important; border: none !important; padding: 0 !important; margin: 0 !important; }

/* ── 슬라이더 숫자 입력칸 너비 축소 ── */
.gradio-slider input[type="number"] {
    width: 48px !important;
    min-width: 0 !important;
    padding: 0 4px !important;
}

/* -- 파일 목록 -- */
#wn-file-list {
    max-height: 220px;
    overflow-y: auto;
    background: #0d1117;
    border: 1px solid #1e2130;
    border-radius: 8px;
    padding: 4px 0;
}
.wn-file-item {
    display: flex;
    align-items: center;
    padding: 5px 10px;
    cursor: pointer;
    border-radius: 4px;
    margin: 1px 4px;
    transition: background .1s;
    color: #9ca3af;
    font-size: 0.84rem;
    font-family: 'JetBrains Mono', monospace;
    user-select: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.wn-file-item:hover { background: #1e2130; color: #e5e7eb; }
.wn-file-item.selected { background: #1e2d4a; color: #818cf8; }
.wn-file-empty {
    padding: 16px;
    text-align: center;
    color: #4b5563;
    font-size: 0.82rem;
}
.wn-hidden-input {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
"""

# ---------------------------------------------------------------------------
# 로직 함수
# ---------------------------------------------------------------------------

def handle_start_recording(device_idx, cat_data_val, l1_id, l2_id, l3_id, chunk_minutes,
                           model_name, summary_type_val):
    _fail = lambda msg: (gr.update(interactive=True), gr.update(interactive=False),
                         gr.update(interactive=False, value="⏸ 일시정지"),
                         gr.update(interactive=True, value="마이크 테스트"), msg, "")
    out_dir = _wav_dir(cat_data_val, l1_id, l2_id, l3_id)
    chunk_min = int(chunk_minutes or 0)
    if device_idx == _WASAPI_AUTO:
        file_path, msg = recorder.start(device_override=None, mixed=True, output_dir=out_dir, chunk_minutes=chunk_min)
    elif device_idx == _MIX_AUTO:
        rdp_idx, _ = recorder.find_rdp_device()
        if rdp_idx is None:
            return _fail("원격 마이크를 찾을 수 없습니다.\n"
                         "RDP 클라이언트(원격 데스크톱 연결) → '옵션 더 보기' → '로컬 장치 및 리소스'\n"
                         "→ '오디오 녹음' 항목을 활성화한 뒤 재연결하세요.")
        file_path, msg = recorder.start(device_override=rdp_idx, mixed=True, output_dir=out_dir, chunk_minutes=chunk_min)
    else:
        if device_idx == _LOOPBACK_AUTO:
            loopback_idx, _ = recorder.find_loopback_device()
            if loopback_idx is None:
                return _fail("루프백 장치를 찾을 수 없습니다.\n"
                             "Windows 사운드 설정 → 녹음 탭 → 'Stereo Mix' 활성화 후 재시도하거나,\n"
                             "'(PC) 🎧 원격회의' 옵션을 사용해보세요.")
            device = loopback_idx
        elif device_idx == _REMOTE_AUTO:
            rdp_idx, _ = recorder.find_rdp_device()
            if rdp_idx is None:
                return _fail("원격 마이크를 찾을 수 없습니다.\n"
                             "RDP 클라이언트(원격 데스크톱 연결) → '옵션 더 보기' → '로컬 장치 및 리소스'\n"
                             "→ '오디오 녹음' 항목을 활성화한 뒤 재연결하세요.\n"
                             "또는 설정 탭에서 [장치 목록 조회]로 [원격] 장치를 직접 선택하세요.")
            device = rdp_idx
        elif device_idx is None or device_idx == -1:
            device = None
        else:
            device = int(device_idx)
        file_path, msg = recorder.start(device_override=device, output_dir=out_dir, chunk_minutes=chunk_min)
    if file_path:
        p = Path(file_path)
        base = p.stem.split("_part")[0]
        transcript_out = _out_dir(cat_data_val, l1_id, l2_id, l3_id)
        auto_worker.reset(
            combined_path=transcript_out / f"{base}_transcript.txt",
            out_dir=transcript_out,
            model_name=model_name,
            summary_type=summary_type_val,
        )
        return (
            gr.update(interactive=False),                        # btn_start
            gr.update(interactive=True),                         # btn_stop
            gr.update(interactive=True, value="⏸ 일시정지"),    # btn_pause
            gr.update(interactive=False, value="마이크 테스트"), # btn_test
            msg,
            file_path,
        )
    return (
        gr.update(interactive=True),
        gr.update(interactive=False),
        gr.update(interactive=False, value="⏸ 일시정지"),
        gr.update(interactive=True, value="마이크 테스트"),
        msg,
        "",
    )


def handle_stop_recording():
    file_path, msg = recorder.stop()
    return (
        gr.update(interactive=True),                             # btn_start
        gr.update(interactive=False),                            # btn_stop
        gr.update(interactive=False, value="⏸ 일시정지"),       # btn_pause (초기화)
        gr.update(interactive=True, value="마이크 테스트"),      # btn_test
        msg,
        file_path or "",
    )


def handle_pause_resume():
    """일시정지 ↔ 재개 토글."""
    if recorder.paused:
        msg = recorder.resume()
        return gr.update(value="⏸ 일시정지"), msg
    else:
        msg = recorder.pause()
        return gr.update(value="▶ 재개"), msg


def handle_chunk_poll(current_view: str):
    """2초마다 청크/전사/요약 상태를 폴링해 UI 갱신. 타이머 active 자체 제어."""
    r_status     = gr.update()
    r_file       = gr.update()
    r_transcript = gr.update()
    r_tfile      = gr.update()
    r_correction = gr.update()
    r_cfile      = gr.update()
    r_pipeline   = gr.update()
    r_display    = gr.update()
    r_view       = gr.update()
    r_dfile      = gr.update()
    r_summary    = gr.update()
    r_sfile      = gr.update()

    # 청크 알림
    msg = recorder.pop_chunk_message()
    if msg:
        r_status = gr.update(value=msg)
        if recorder.current_file:
            r_file = gr.update(value=str(recorder.current_file))

    # 전사 대기 작업 → worker 큐로 이동
    job = recorder.pop_pending_transcription()
    while job is not None:
        auto_worker.enqueue(job)
        job = recorder.pop_pending_transcription()

    # 녹음 종료 + recorder 큐 소진 + worker 아직 안 끝난 경우: 자동 교정 예약
    if (
        not recorder.recording
        and auto_worker._session_active
        and not auto_worker._finalize_triggered
        and not auto_worker.is_busy()
    ):
        auto_worker.enqueue_finalize()

    # 완료된 결과 반영
    result = auto_worker.pop_result()
    while result is not None:
        if "error" in result:
            r_pipeline = gr.update(value=f"⚠ {result['error']}")
        elif result.get("type") == "transcript":
            r_transcript = gr.update(value=result["transcript"])
            r_tfile      = gr.update(value=result["file_path"])
            r_pipeline   = gr.update(value=result["status"])
            if current_view == "원문":
                r_display = gr.update(value=result["transcript"])
                r_dfile   = gr.update(value=result["file_path"])
        elif result.get("type") == "correction":
            r_correction = gr.update(value=result["correction"])
            r_cfile      = gr.update(value=result["file_path"])
            r_pipeline   = gr.update(value=result["status"])
            r_display    = gr.update(value=result["correction"])
            r_view       = gr.update(value="교정")
            r_dfile      = gr.update(value=result["file_path"])
        elif result.get("type") == "summary":
            r_summary  = gr.update(value=result["summary"])
            r_sfile    = gr.update(value=result["file_path"])
            r_pipeline = gr.update(value=result["status"])
        result = auto_worker.pop_result()

    # 대기열 현황 텍스트 갱신
    queue_text = auto_worker.get_status_text()
    r_queue = gr.update(value=queue_text)

    still_busy = recorder.recording or auto_worker.is_busy()
    r_timer = gr.update(active=still_busy)

    return r_status, r_file, r_transcript, r_tfile, r_correction, r_cfile, r_pipeline, r_queue, r_timer, r_display, r_view, r_dfile, r_summary, r_sfile


def handle_mic_test(device_idx):
    """마이크 테스트 토글."""
    if recorder.testing:
        msg = recorder.stop_test()
        return gr.update(value="마이크 테스트"), msg
    else:
        if device_idx == _WASAPI_AUTO:
            msg = recorder.start_test(mixed=True)
        elif device_idx == _MIX_AUTO:
            rdp_idx, _ = recorder.find_rdp_device()
            if rdp_idx is None:
                return gr.update(value="마이크 테스트"), ("원격 마이크를 찾을 수 없습니다.\n"
                    "RDP 클라이언트에서 '오디오 녹음' 리다이렉션을 활성화한 뒤 재연결하세요.")
            msg = recorder.start_test(device_override=rdp_idx, mixed=True)
        elif device_idx == _LOOPBACK_AUTO:
            loopback_idx, _ = recorder.find_loopback_device()
            msg = recorder.start_test(device_override=loopback_idx)
        elif device_idx == _REMOTE_AUTO:
            rdp_idx, _ = recorder.find_rdp_device()
            if rdp_idx is None:
                return gr.update(value="마이크 테스트"), ("원격 마이크를 찾을 수 없습니다.\n"
                    "RDP 클라이언트에서 '오디오 녹음' 리다이렉션을 활성화한 뒤 재연결하세요.")
            msg = recorder.start_test(device_override=rdp_idx)
        elif device_idx is None or device_idx == -1:
            msg = recorder.start_test(device_override=None)
        else:
            msg = recorder.start_test(device_override=int(device_idx))
        if "실패" in msg:
            return gr.update(value="마이크 테스트"), msg
        return gr.update(value="테스트 중지"), msg


# ---------------------------------------------------------------------------
# 카테고리 헬퍼
# ---------------------------------------------------------------------------

def _cat_choices(data: list, parent_id) -> list:
    return [(i["name"], i["id"]) for i in cat_mod.get_level_items(data, parent_id)]

def _col_header(level: int, parent_name: str | None = None) -> str:
    labels = {1: "대분류", 2: "중분류", 3: "소분류"}
    base = labels[level]
    suffix = f" ({parent_name})" if parent_name and level > 1 else ""
    return f'<div class="wn-cat-col-header">{base}{suffix}</div>'

def _path_html(data: list, l1, l2, l3) -> str:
    parts = [cat_mod.get_name(data, x) for x in (l1, l2, l3) if x]
    if not parts:
        return '<div class="wn-cat-path">분류 미선택</div>'
    return f'<div class="wn-cat-path wn-cat-path-active">📁 outputs/{" / ".join(parts)}/</div>'

def _out_dir(data: list, l1, l2, l3):
    n1, n2, n3 = (cat_mod.get_name(data, x) for x in (l1, l2, l3))
    return storage.resolve_out_dir(n1, n2, n3)

def _wav_dir(data: list, l1, l2, l3):
    n1, n2, n3 = (cat_mod.get_name(data, x) for x in (l1, l2, l3))
    return storage.resolve_wav_dir(n1, n2, n3)

# 패널 열기/닫기
def cat_open_panel():  return gr.update(visible=True)
def cat_close_panel(): return gr.update(visible=False)

# L1 radio 선택 → L2 초기화, 헤더 갱신, 드롭다운 갱신
def on_panel_l1(data, l1_id):
    l1_ch = _cat_choices(data, None)
    l2_ch = _cat_choices(data, l1_id)
    l1n = cat_mod.get_name(data, l1_id)
    return (
        gr.update(choices=l2_ch, value=None),
        gr.update(choices=[], value=None),
        gr.update(value=_col_header(2, l1n)),
        gr.update(value=_col_header(3, None)),
        gr.update(choices=l1_ch, value=l1_id),
        gr.update(choices=l2_ch, value=None),
        gr.update(choices=[], value=None),
        _path_html(data, l1_id, None, None),
    )

# L2 radio 선택 → L3 초기화, 헤더 갱신, 드롭다운 갱신
def on_panel_l2(data, l1_id, l2_id):
    l2_ch = _cat_choices(data, l1_id)
    l3_ch = _cat_choices(data, l2_id)
    l2n = cat_mod.get_name(data, l2_id)
    return (
        gr.update(choices=l3_ch, value=None),
        gr.update(value=_col_header(3, l2n)),
        gr.update(choices=l2_ch, value=l2_id),
        gr.update(choices=l3_ch, value=None),
        _path_html(data, l1_id, l2_id, None),
    )

# L3 radio 선택 → 드롭다운 + 경로 갱신
def on_panel_l3(data, l1_id, l2_id, l3_id):
    l3_ch = _cat_choices(data, l2_id)
    return gr.update(choices=l3_ch, value=l3_id), _path_html(data, l1_id, l2_id, l3_id)

# 메인 드롭다운 cascade
def on_l1_change(data, l1_id):
    l2_ch = _cat_choices(data, l1_id)
    return gr.update(choices=l2_ch, value=None), gr.update(choices=[], value=None), _path_html(data, l1_id, None, None)

def on_l2_change(data, l1_id, l2_id):
    l3_ch = _cat_choices(data, l2_id)
    return gr.update(choices=l3_ch, value=None), _path_html(data, l1_id, l2_id, None)

def on_l3_change(data, l1_id, l2_id, l3_id):
    return _path_html(data, l1_id, l2_id, l3_id)

# 추가 시작
def cat_start_add(ctx, col, parent_id=None):
    lbl = {1: "대분류 추가", 2: "중분류 추가", 3: "소분류 추가"}
    return (
        {"col": col, "action": "add", "item_id": "", "parent_id": parent_id},
        gr.update(visible=True),
        gr.update(value="", label=lbl[col]),
        "",
    )

# 수정 시작
def cat_start_edit(data, ctx, col, item_id):
    if not item_id:
        return ctx, gr.update(visible=False), gr.update(), ""
    lbl = {1: "대분류 수정", 2: "중분류 수정", 3: "소분류 수정"}
    name = cat_mod.get_name(data, item_id) or ""
    return (
        {"col": col, "action": "edit", "item_id": item_id, "parent_id": None},
        gr.update(visible=True),
        gr.update(value=name, label=lbl[col]),
        "",
    )

# 취소
def cat_cancel(ctx):
    return {"col": 0, "action": "", "item_id": "", "parent_id": None}, gr.update(visible=False), ""

# 확인 (추가/수정 저장)
def cat_confirm(data, ctx, input_val, l1_id, l2_id, l3_id):
    name = input_val.strip()
    if not name:
        return data, ctx, gr.update(), gr.update(), gr.update(), gr.update(visible=True), "⚠ 이름을 입력하세요."
    col, action = ctx["col"], ctx["action"]
    pid, iid = ctx.get("parent_id"), ctx.get("item_id", "")
    if action == "add":
        data = cat_mod.add_item(data, name, pid)
    elif action == "edit" and iid:
        data = cat_mod.rename_item(data, iid, name)
    cat_mod.save(data)
    l1c = _cat_choices(data, None)
    l2c = _cat_choices(data, l1_id) if l1_id else []
    l3c = _cat_choices(data, l2_id) if l2_id else []
    empty = {"col": 0, "action": "", "item_id": "", "parent_id": None}
    return (
        data, empty,
        gr.update(choices=l1c, value=l1_id),
        gr.update(choices=l2c, value=l2_id),
        gr.update(choices=l3c, value=l3_id),
        gr.update(visible=False), "",
    )

# 삭제
def cat_delete(data, col, item_id, l1_id, l2_id, l3_id):
    if not item_id:
        return data, gr.update(), gr.update(), gr.update(), "⚠ 삭제할 항목을 선택하세요.", gr.update(), gr.update(), gr.update(), _path_html(data, l1_id, l2_id, l3_id)
    n = cat_mod.count_descendants(data, item_id)
    item_name = cat_mod.get_name(data, item_id)
    data = cat_mod.delete_item(data, item_id)
    cat_mod.save(data)
    # 삭제된 항목이 선택 중이면 초기화
    nl1 = None if l1_id == item_id else l1_id
    nl2 = None if l2_id == item_id or nl1 is None else l2_id
    nl3 = None if l3_id == item_id or nl2 is None else l3_id
    l1c = _cat_choices(data, None)
    l2c = _cat_choices(data, nl1) if nl1 else []
    l3c = _cat_choices(data, nl2) if nl2 else []
    msg = f"🗑 '{item_name}' 삭제 (하위 {n}개 포함)" if n else f"🗑 '{item_name}' 삭제"
    return (
        data,
        gr.update(choices=l1c, value=nl1),
        gr.update(choices=l2c, value=nl2),
        gr.update(choices=l3c, value=nl3),
        msg,
        gr.update(value=nl1, choices=l1c),
        gr.update(value=nl2, choices=l2c),
        gr.update(value=nl3, choices=l3c),
        _path_html(data, nl1, nl2, nl3),
    )

# 초기 로드
def init_cat_ui(data):
    ch = _cat_choices(data, None)
    return gr.update(choices=ch, value=None), gr.update(choices=ch, value=None)

# 패널 닫기 + 드롭다운 choices 재동기화 (cascade 순서 문제 방지)
def sync_dropdowns_on_close(data, l1_id, l2_id):
    l2_ch = _cat_choices(data, l1_id)
    l3_ch = _cat_choices(data, l2_id)
    return gr.update(visible=False), gr.update(choices=l2_ch), gr.update(choices=l3_ch)


def handle_open_folder(path: str):
    if not path:
        return
    import subprocess
    target = Path(path.strip())
    folder = target.parent if target.is_file() else target
    if not folder.exists():
        return
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(folder)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])


def _resolve_audio(recorded: str, uploaded: str | None) -> str | None:
    return recorded if recorded else uploaded


# ── 파일 목록 헬퍼 ──────────────────────────────────────

def _scan_audio_files(folder) -> list:
    """폴더에서 오디오 파일을 파일명 오름차순으로 반환."""
    if not folder or not Path(folder).exists():
        return []
    exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}
    files = sorted(
        [str(f) for f in Path(folder).iterdir() if f.suffix.lower() in exts],
        key=lambda p: Path(p).name.lower(),
    )
    return files


def _render_file_list(paths: list) -> str:
    """파일 목록 HTML 렌더링."""
    if not paths:
        return '<div id="wn-file-list"><div class="wn-file-empty">파일 없음</div></div>'
    items = ""
    for p in paths:
        name = Path(p).name
        items += (
            f'<div class="wn-file-item" data-path="{p}" title="{p}">'
            f'<span class="wn-file-name">{name}</span>'
            f'</div>'
        )
    return f'<div id="wn-file-list">{items}</div>'


def load_folder_file_list(cat_data_val, l1_id, l2_id, l3_id):
    """분류 폴더 기반 파일 목록 로드."""
    folder = _out_dir(cat_data_val, l1_id, l2_id, l3_id)
    wav_folder = _wav_dir(cat_data_val, l1_id, l2_id, l3_id)
    paths = _scan_audio_files(wav_folder)
    if wav_folder != folder:
        paths += _scan_audio_files(folder)
    paths = sorted(set(paths), key=lambda p: Path(p).name.lower())
    html = _render_file_list(paths)
    count = f"전체 {len(paths)}개" if paths else ""
    return html, paths, count


def handle_upload_files(files, current_paths: list):
    """파일 추가 업로드 처리."""
    if not files:
        return _render_file_list(current_paths), current_paths, f"전체 {len(current_paths)}개"
    uploaded = [f if isinstance(f, str) else f.name for f in files]
    merged = sorted(set(current_paths + uploaded), key=lambda p: Path(p).name.lower())
    html = _render_file_list(merged)
    count = f"전체 {len(merged)}개"
    return html, merged, count


def handle_file_selection(selected_json: str, file_paths: list):
    """선택된 파일 경로 JSON -> Audio 로드 + 선택 카운트."""
    import json
    try:
        selected = json.loads(selected_json) if selected_json else []
    except Exception:
        selected = []
    audio_val = selected[0] if selected else None
    count = f"선택 {len(selected)}개" if selected else ""
    return audio_val, count


def handle_clear_file_list():
    """파일 목록 비우기."""
    return _render_file_list([]), [], "", None, ""


def handle_remove_selected(selected_json: str, file_paths_val: list):
    """선택된 파일을 목록에서 제거."""
    import json as _j
    try:
        selected = set(_j.loads(selected_json)) if selected_json else set()
    except Exception:
        selected = set()
    remaining = [p for p in file_paths_val if p not in selected]
    html = _render_file_list(remaining)
    count = f"전체 {len(remaining)}개" if remaining else ""
    return html, remaining, count, ""   # selected_paths 초기화


def _on_file_select(selected_json: str, file_paths_val: list):
    """파일 선택 → audio_preview, file_count_label, uploaded_file 갱신."""
    import json as _j
    try:
        selected = _j.loads(selected_json) if selected_json else []
    except Exception:
        selected = []
    audio_val = selected[0] if selected else None
    count_html = (
        f'<span style="color:#818cf8;font-size:.82rem">{len(selected)}개 선택</span>'
        if selected else ""
    )
    return audio_val, count_html, audio_val or ""


def handle_transcribe(recorded: str, uploaded: str | None, cat_data_val, l1_id, l2_id, l3_id, progress=gr.Progress()):
    _no = (gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
    audio = _resolve_audio(recorded, uploaded)
    if not audio:
        return "", "", "", "오디오 파일을 선택하거나 먼저 녹음하세요.", *_no
    try:
        progress(0.1, desc="전사 시작...")
        transcript, out_file = transcriber.transcribe(
            audio,
            on_progress=lambda pct, m: progress(pct, desc=m),
            output_dir=_out_dir(cat_data_val, l1_id, l2_id, l3_id),
        )
        progress(1.0, desc="전사 완료!")
        return (transcript, out_file, "", f"완료 — {Path(out_file).name}",
                gr.update(value=transcript), gr.update(value=out_file),
                gr.update(value="원문"), gr.update(value=""), gr.update(value=""))
    except Exception as exc:
        return "", "", "", f"전사 실패: {exc}", *_no


def handle_correct(
    transcript: str,
    recorded: str,
    uploaded: str | None,
    model_name: str,
    merged_stem: str,
    cat_data_val, l1_id, l2_id, l3_id,
    progress=gr.Progress(),
):
    _no = (gr.update(), gr.update(), gr.update())
    if not transcript:
        return "", "", "먼저 전사를 실행하세요.", *_no
    if merged_stem:
        audio_stem = merged_stem
    else:
        audio = _resolve_audio(recorded, uploaded)
        audio_stem = Path(audio).stem if audio else "output"
    try:
        progress(0.2, desc="교정 중...")
        corrected, out_file = summarizer.correct_transcript(
            transcript, audio_stem, model=model_name,
            output_dir=_out_dir(cat_data_val, l1_id, l2_id, l3_id),
        )
        progress(1.0, desc="교정 완료!")
        return (corrected, out_file, f"완료 — {Path(out_file).name}",
                gr.update(value=corrected), gr.update(value="교정"), gr.update(value=out_file))
    except Exception as exc:
        return "", "", f"교정 실패: {exc}", *_no


def handle_load_transcripts(files):
    _no = (gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
    if not files:
        return "", "", "전사 파일을 선택하세요.", *_no
    sorted_files = sorted(files, key=lambda f: Path(f).name)
    parts = []
    for f in sorted_files:
        parts.append(Path(f).read_text(encoding="utf-8"))
    merged = "\n\n".join(parts)
    first_stem = Path(sorted_files[0]).stem.replace("_transcript", "")
    merged_stem = f"{first_stem}_merged"
    return (merged, merged_stem, f"전사 파일 {len(sorted_files)}개 병합 완료",
            gr.update(value=merged), gr.update(value=""), gr.update(value="원문"),
            gr.update(value=""), gr.update(value=""))


def handle_summarize(
    correction: str,
    transcript: str,
    recorded: str,
    uploaded: str | None,
    model_name: str,
    merged_stem: str,
    summary_type_val: str,
    cat_data_val, l1_id, l2_id, l3_id,
    progress=gr.Progress(),
):
    text = correction.strip() if correction.strip() else transcript.strip()
    if not text:
        return "", "", "먼저 전사를 실행하세요."
    if merged_stem:
        audio_stem = merged_stem
    else:
        audio = _resolve_audio(recorded, uploaded)
        audio_stem = Path(audio).stem if audio else "output"
    try:
        progress(0.2, desc="Ollama 요약 중...")
        summary, out_file = summarizer.summarize(
            text, audio_stem, model=model_name,
            output_dir=_out_dir(cat_data_val, l1_id, l2_id, l3_id),
            summary_type=summary_type_val,
        )
        progress(1.0, desc="요약 완료!")
        return summary, out_file, f"완료 — {Path(out_file).name}"
    except Exception as exc:
        return "", "", f"요약 실패: {exc}"


def handle_pipeline(
    recorded: str,
    uploaded: str | None,
    model_name: str,
    summary_type_val: str,
    cat_data_val, l1_id, l2_id, l3_id,
    progress=gr.Progress(),
):
    _disp_no = (gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
    audio = _resolve_audio(recorded, uploaded)
    if not audio:
        return "", "", "", "", "오디오 파일을 선택하거나 먼저 녹음하세요.", "", *_disp_no
    out_dir = _out_dir(cat_data_val, l1_id, l2_id, l3_id)
    audio_stem = Path(audio).stem
    try:
        progress(0.05, desc="전사 시작...")
        transcript, t_file = transcriber.transcribe(
            audio,
            on_progress=lambda pct, m: progress(pct * 0.65, desc=m),
            output_dir=out_dir,
        )
        if not transcript:
            return "", t_file, "", "", "전사 결과가 비어 있습니다.", "", *_disp_no

        corrected_text = transcript
        c_file = ""
        try:
            progress(0.68, desc="교정 중...")
            corrected_text, c_file = summarizer.correct_transcript(
                transcript, audio_stem, model=model_name, output_dir=out_dir,
            )
            progress(0.72, desc="교정 완료")
        except Exception as exc:
            print(f"[교정] 실패 (원문으로 진행): {exc}", flush=True)

        progress(0.75, desc="요약 중...")
        summary, s_file = summarizer.summarize(
            corrected_text, audio_stem, model=model_name, output_dir=out_dir,
            summary_type=summary_type_val,
        )
        progress(1.0, desc="완료!")
        return (
            transcript, t_file,
            summary, s_file,
            f"완료 — {Path(t_file).name} / {Path(s_file).name}",
            "",
            gr.update(value=corrected_text), gr.update(value=c_file or t_file),
            gr.update(value="교정" if c_file else "원문"), corrected_text, c_file,
        )
    except Exception as exc:
        return "", "", "", "", f"실패: {exc}", "", *_disp_no


def handle_file_list_process(
    selected_json: str,
    file_paths: list,
    action: str,
    model_name: str,
    summary_type_val: str,
    cat_data_val, l1_id, l2_id, l3_id,
    progress=gr.Progress(),
):
    """파일 목록에서 선택된 파일 처리. outputs: 11개 (handle_pipeline 기준)."""
    import json as _json
    _no11 = tuple(gr.update() for _ in range(11))
    try:
        selected = _json.loads(selected_json) if selected_json else []
    except Exception:
        selected = []
    if not selected:
        return *_no11[:10], "선택된 파일이 없습니다."

    out_dir = _out_dir(cat_data_val, l1_id, l2_id, l3_id)

    if len(selected) == 1:
        audio = selected[0]
        if action == "pipeline":
            # handle_pipeline: 11개 반환
            return handle_pipeline(audio, None, model_name, summary_type_val, cat_data_val, l1_id, l2_id, l3_id, progress)
        elif action == "transcribe":
            # handle_transcribe: 9개 반환
            # (transcript, t_file, merged_stem, status, text_display, display_file_path, view_radio, correction_output, corrected_file_path)
            res = handle_transcribe(audio, None, cat_data_val, l1_id, l2_id, l3_id, progress)
            # outputs(11): transcript_output, transcript_file_path, summary_output, summary_file_path,
            #              pipeline_status, merged_stem_state,
            #              text_display, display_file_path, view_radio, correction_output, corrected_file_path
            return (res[0], res[1],
                    gr.update(), gr.update(),
                    res[3], res[2],
                    res[4], res[5], res[6], res[7], res[8])
        else:
            return *_no11[:10], "전사 결과를 먼저 실행하세요."
    else:
        audio_stem_base = Path(selected[0]).stem
        combined_path = out_dir / f"{audio_stem_base}_merged_transcript.txt"
        auto_worker.reset(
            combined_path=combined_path,
            out_dir=out_dir,
            model_name=model_name,
            summary_type=summary_type_val if action == "pipeline" else "회의",
        )
        for path in selected:
            auto_worker.enqueue_file(path)
        if action in ("pipeline", "transcribe"):
            auto_worker.enqueue_finalize()
        msg = f"처리 시작 - {len(selected)}개 파일"
        return *_no11[:10], msg


def refresh_ollama_models():
    models = summarizer.get_available_models()
    if not models:
        return gr.update(choices=[OLLAMA_MODEL], value=OLLAMA_MODEL), \
               '<div class="wn-cat-path" style="color:#ef4444">⚠ Ollama 연결 실패 — ollama serve 실행 여부 확인</div>'
    value = OLLAMA_MODEL if OLLAMA_MODEL in models else models[0]
    return gr.update(choices=models, value=value), ""


def list_audio_devices():
    return recorder.list_devices()


def get_input_device_choices():
    """UI 드롭다운용 (레이블, 인덱스) 선택지 목록 반환."""
    import sounddevice as sd
    choices = [
        ("(PC) 🎙 대면회의", -1),
        ("(PC) 🎙+🎧 원격회의", _WASAPI_AUTO),
        ("(원격) 🖥 대면회의", _REMOTE_AUTO),
        ("(원격) 🎙+🎧 원격회의", _MIX_AUTO),
    ]
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            tag = " [루프백]" if is_loopback_device_name(dev["name"]) else (
                " [원격]" if is_rdp_device_name(dev["name"]) else ""
            )
            choices.append((f"[{i}] {dev['name']}{tag}", i))
    return choices


_last_heartbeat: float = float("inf")  # 첫 폴링 전까지 타임아웃 억제

async def _api_level():
    """레벨 미터 데이터를 JSON으로 반환하는 FastAPI 핸들러."""
    global _last_heartbeat
    import time as _t
    _last_heartbeat = _t.monotonic()
    _no_elapsed = {"total": None, "part": None, "part_index": 1, "has_parts": False}
    if recorder.paused:
        return {"status": "paused", **recorder.get_elapsed()}
    if recorder.recording or recorder.testing:
        elapsed = recorder.get_elapsed() if recorder.recording else _no_elapsed
        return {"status": "active", "level": recorder.get_level(), "testing": bool(recorder.testing), **elapsed}
    return {"status": "idle", **_no_elapsed}


# 레벨 미터를 JavaScript setInterval로 직접 갱신 (Gradio SSE 교체 → 깜빡임 제거)
_LEVEL_JS = """() => {
  setInterval(async function() {
    try {
      var d = await (await fetch('/api/level')).json();
      var el = document.getElementById('wn-level-inner');
      if (!el) return;
      if (d.status === 'paused') {
        el.style.color = '#4b5563';
        el.textContent = '⏸ 일시정지됨';
      } else if (d.status === 'active') {
        var lv = d.level;
        var filled = Math.round(lv * 0.30);
        var bar = '█'.repeat(filled) + '░'.repeat(30 - filled);
        el.style.color = lv > 80 ? '#ef4444' : '#6ee7b7';
        el.innerHTML = (d.testing ? '테스트 ' : '') + bar + '&nbsp;' + Math.round(lv) + '%';
      } else {
        el.style.color = '#4b5563';
        el.textContent = '마이크 대기 중';
      }
      var te = document.getElementById('wn-timer-inner');
      if (te) {
        te.style.whiteSpace = 'nowrap';
        if (d.total) {
          var txt = d.has_parts
            ? '⏱ 전체 ' + d.total + '   파트' + d.part_index + ' ' + d.part
            : '⏱ ' + d.total;
          te.textContent = (d.status === 'paused' ? '⏸ ' : '') + txt;
          te.style.color = d.status === 'paused' ? '#f59e0b' : '#6ee7b7';
        } else {
          te.textContent = '대기 중';
          te.style.color = '#4b5563';
        }
      }
    } catch(e) {}
  }, 200);
}"""

_FILE_LIST_JS = """() => {
  function setupFileList() {
    var list = document.getElementById('wn-file-list');
    if (!list) { setTimeout(setupFileList, 500); return; }
    var selected = [];
    list.addEventListener('click', function(e) {
      var item = e.target.closest('.wn-file-item');
      if (!item) return;
      var path = item.dataset.path;
      if (e.ctrlKey || e.metaKey) {
        var idx = selected.indexOf(path);
        if (idx >= 0) { selected.splice(idx, 1); item.classList.remove('selected'); }
        else { selected.push(path); item.classList.add('selected'); }
      } else {
        list.querySelectorAll('.wn-file-item.selected').forEach(function(el) { el.classList.remove('selected'); });
        selected = [path];
        item.classList.add('selected');
      }
      var tb = document.querySelector('#wn-selected-paths textarea');
      if (tb) {
        tb.value = JSON.stringify(selected);
        tb.dispatchEvent(new Event('input', {bubbles: true}));
      }
    });
    var obs = new MutationObserver(function() { selected = []; });
    obs.observe(list, {childList: true});

    // + 버튼 → 숨겨진 파일 업로드 input 클릭
    var addBtn = document.querySelector('#wn-file-add-btn button');
    if (addBtn) {
      addBtn.addEventListener('click', function() {
        var fileInput = document.querySelector('#wn-file-upload input[type=file]');
        if (fileInput) fileInput.click();
      });
    }
  }
  setupFileList();
}"""


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

with gr.Blocks(css=CSS, title="WhisperNote") as demo:

    # ── 헤더 ──
    gr.HTML(f"""
    <div id="wn-header">
        <h1>WhisperNote</h1>
        <p>회의 녹음 &nbsp;·&nbsp; 화자 분리 &nbsp;·&nbsp; 전사 &nbsp;·&nbsp; 요약 &nbsp;—&nbsp; 완전 로컬</p>
        <span style="display:inline-block;margin-top:.5rem;padding:.2rem .7rem;background:#1e2130;border:1px solid #2d3348;border-radius:999px;font-size:.72rem;font-family:'JetBrains Mono',monospace;color:#6b7280;letter-spacing:.04em;">v{__version__}</span>
    </div>
    """)

    with gr.Tabs(elem_classes="wn-tabs"):

        # ════════════════════════════════════════════════════════
        # Tab 1 : 메인
        # ════════════════════════════════════════════════════════
        with gr.TabItem("  Studio  "):

            # ── State ──
            cat_data    = gr.State(cat_mod.load())
            cat_edit_ctx = gr.State({"col": 0, "action": "", "item_id": "", "parent_id": None})
            merged_stem_state = gr.State("")
            file_paths   = gr.State([])

            # ════════════════════════════════════════════════════════
            # 분류 설정 패널 (전체 너비, 기본 숨김)
            # ════════════════════════════════════════════════════════
            with gr.Column(visible=False, elem_id="cat-panel", elem_classes="wn-card wn-cat-panel") as cat_panel:
                gr.HTML('<div class="wn-label" style="margin:0 0 0.6rem">📁 분류 설정</div>')
                btn_cat_close = gr.Button("✕ 접기", elem_id="btn-cat-close", elem_classes="wn-btn-secondary", min_width=70, scale=0)
                with gr.Row(equal_height=False):
                    with gr.Column(scale=1, elem_classes="wn-cat-col"):
                        cat1_header = gr.HTML(_col_header(1))
                        cat1_radio  = gr.Radio(choices=[], label="", show_label=False, elem_classes="wn-cat-radio")
                        with gr.Row():
                            btn_cat1_add  = gr.Button("＋ 추가", elem_classes="wn-cat-btn-sm", min_width=50)
                            btn_cat1_edit = gr.Button("✏ 수정", elem_classes="wn-cat-btn-sm", min_width=50)
                            btn_cat1_del  = gr.Button("✕ 삭제", elem_classes="wn-cat-btn-sm wn-cat-btn-del", min_width=50)
                    with gr.Column(scale=1, elem_classes="wn-cat-col"):
                        cat2_header = gr.HTML(_col_header(2))
                        cat2_radio  = gr.Radio(choices=[], label="", show_label=False, elem_classes="wn-cat-radio")
                        with gr.Row():
                            btn_cat2_add  = gr.Button("＋ 추가", elem_classes="wn-cat-btn-sm", min_width=50)
                            btn_cat2_edit = gr.Button("✏ 수정", elem_classes="wn-cat-btn-sm", min_width=50)
                            btn_cat2_del  = gr.Button("✕ 삭제", elem_classes="wn-cat-btn-sm wn-cat-btn-del", min_width=50)
                    with gr.Column(scale=1, elem_classes="wn-cat-col"):
                        cat3_header = gr.HTML(_col_header(3))
                        cat3_radio  = gr.Radio(choices=[], label="", show_label=False, elem_classes="wn-cat-radio")
                        with gr.Row():
                            btn_cat3_add  = gr.Button("＋ 추가", elem_classes="wn-cat-btn-sm", min_width=50)
                            btn_cat3_edit = gr.Button("✏ 수정", elem_classes="wn-cat-btn-sm", min_width=50)
                            btn_cat3_del  = gr.Button("✕ 삭제", elem_classes="wn-cat-btn-sm wn-cat-btn-del", min_width=50)
                with gr.Row(visible=False) as cat_input_row:
                    cat_input  = gr.Textbox(show_label=True, label="항목 이름", placeholder="이름 입력", scale=4)
                    btn_cat_ok     = gr.Button("확인", elem_classes="wn-btn-secondary", scale=1, min_width=60)
                    btn_cat_cancel = gr.Button("취소", elem_classes="wn-cat-btn-sm wn-cat-btn-del", scale=1, min_width=60)
                cat_panel_msg = gr.HTML("")

            # ── 분류 (전체 너비) ──────────────────────────────────
            with gr.Column(elem_classes="wn-card"):
                gr.HTML('<div class="wn-label">분류</div>')
                with gr.Row():
                    cat_l1 = gr.Dropdown(label="대분류", choices=[], value=None, interactive=True, elem_classes="wn-dropdown", scale=3)
                    cat_l2 = gr.Dropdown(label="중분류", choices=[], value=None, interactive=True, elem_classes="wn-dropdown", scale=3)
                    cat_l3 = gr.Dropdown(label="소분류", choices=[], value=None, interactive=True, elem_classes="wn-dropdown", scale=3)
                    btn_cat_settings = gr.Button("⚙", elem_id="btn-cat-settings", scale=0, min_width=42)
                cat_path_display = gr.HTML('<div class="wn-cat-path">분류 미선택</div>')

            # ── 녹음 (전체 너비) ──────────────────────────────────
            with gr.Column(elem_classes="wn-card"):
                gr.HTML('<div class="wn-label">녹음</div>')
                with gr.Row():
                    input_device = gr.Dropdown(
                        label="입력 장치",
                        choices=[("(PC) 🎙 대면회의", -1)],
                        value=-1,
                        interactive=True,
                        elem_classes="wn-dropdown",
                        scale=3,
                    )
                    mic_gain_slider = gr.Slider(
                        label="🎙 마이크 볼륨",
                        minimum=0.5, maximum=10.0, value=3.0, step=0.5,
                        visible=True, scale=2,
                    )
                    system_gain_slider = gr.Slider(
                        label="🎧 시스템 볼륨",
                        minimum=0.5, maximum=4.0, value=1.0, step=0.1,
                        visible=False, scale=2,
                    )
                    chunk_minutes_input = gr.Number(
                        label="자동 분할 (분)",
                        value=30,
                        minimum=0,
                        maximum=180,
                        step=10,
                        scale=1,
                    )
                    summary_type = gr.Dropdown(
                        label="요약 구분",
                        choices=prompts.list_summary_types(),
                        value="회의",
                        interactive=True,
                        elem_classes="wn-dropdown",
                        scale=1,
                    )
                    ollama_model = gr.Dropdown(
                        label="요약 모델",
                        choices=[OLLAMA_MODEL],
                        value=OLLAMA_MODEL,
                        allow_custom_value=True,
                        interactive=True,
                        elem_classes="wn-dropdown",
                        scale=2,
                    )
                    btn_refresh = gr.Button("↻", elem_classes="wn-btn-secondary", scale=0, min_width=34)
                with gr.Row():
                    btn_start = gr.Button("● 녹음 시작", elem_id="btn-start", scale=2)
                    btn_stop  = gr.Button("■ 녹음 종료", elem_id="btn-stop", interactive=False, scale=2)
                    btn_pause = gr.Button("⏸ 일시정지", elem_classes="wn-btn-secondary", interactive=False, scale=1)
                    btn_test  = gr.Button("마이크 테스트", elem_classes="wn-btn-secondary", scale=1)
                with gr.Row():
                    with gr.Column(scale=2, min_width=0):
                        level_display = gr.HTML(
                            value='<div id="wn-level-inner" class="wn-level-bar" style="color:#4b5563;height:36px;display:flex;align-items:center">마이크 대기 중</div>',
                            elem_id="wn-level-wrap",
                        )
                    with gr.Column(scale=4, min_width=0):
                        timer_display = gr.HTML(
                            value='<div id="wn-timer-inner" style="color:#4b5563;font-size:1.1rem;font-weight:600;letter-spacing:0.05em;height:36px;display:flex;align-items:center;white-space:nowrap">대기 중</div>',
                            elem_id="wn-timer-wrap",
                        )
                with gr.Row():
                    record_status = gr.Textbox(
                        value="대기 중",
                        interactive=False,
                        show_label=False,
                        elem_id="record-status",
                        lines=1,
                        scale=3,
                    )
                    recorded_file = gr.Textbox(
                        interactive=False,
                        show_label=False,
                        placeholder="녹음 후 파일 경로 자동 표시",
                        elem_classes="wn-filepath",
                        lines=1,
                        scale=4,
                    )
                    btn_open_folder = gr.Button("📂 폴더 열기", elem_classes="wn-btn-secondary", scale=1, min_width=90)

            with gr.Row(equal_height=False):

                # ── 왼쪽 패널 ──────────────────────────
                with gr.Column(scale=1, min_width=260, elem_classes="wn-card"):

                    with gr.Row(elem_classes="wn-file-header"):
                        gr.HTML('<div class="wn-label" style="flex:1;margin:0">파일 목록</div>')
                        file_count_label = gr.HTML("")
                        btn_fl_reload = gr.Button("↺", elem_classes="wn-btn-secondary", scale=0, min_width=34)
                        btn_fl_add    = gr.Button("＋", elem_id="wn-file-add-btn", elem_classes="wn-btn-secondary", scale=0, min_width=34)
                        btn_fl_remove = gr.Button("－", elem_classes="wn-cat-btn-sm wn-cat-btn-del", scale=0, min_width=34)
                    file_list_display = gr.HTML(_render_file_list([]))
                    selected_paths = gr.Textbox(
                        elem_id="wn-selected-paths",
                        show_label=False,
                        container=False,
                        elem_classes="wn-hidden-input",
                    )
                    uploaded_files_add = gr.File(
                        label="파일 추가 (드래그 또는 클릭)",
                        file_types=[".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"],
                        file_count="multiple",
                        elem_id="wn-file-upload",
                    )
                    audio_preview = gr.Audio(label="재생", type="filepath", interactive=False)
                    uploaded_file = gr.Textbox(visible=False)

                    model_status = gr.HTML("")

                    gr.HTML('<hr class="wn-divider">')
                    btn_pipeline = gr.Button(
                        "전사 + 요약  →",
                        elem_id="btn-pipeline",
                    )
                    with gr.Row():
                        btn_transcribe = gr.Button(
                            "전사만", elem_classes="wn-btn-secondary", scale=1
                        )
                        btn_summarize = gr.Button(
                            "요약만", elem_classes="wn-btn-secondary", scale=1
                        )

                # ── 오른쪽 결과 패널 ──────────────────────────
                with gr.Column(scale=2, elem_classes="wn-card"):

                    pipeline_status = gr.Textbox(
                        value="",
                        interactive=False,
                        show_label=False,
                        placeholder="처리 상태가 여기에 표시됩니다",
                        lines=1,
                        elem_id="pipeline-status",
                    )
                    queue_status = gr.Textbox(
                        value="",
                        interactive=False,
                        show_label=True,
                        label="자동 처리 대기열",
                        placeholder="대기 중인 작업 없음",
                        lines=3,
                        max_lines=6,
                        elem_id="queue-status",
                        visible=True,
                    )

                    with gr.Row(elem_classes="wn-view-row"):
                        gr.HTML('<div class="wn-label" style="margin-top:.8rem;flex:1">전사 결과</div>')
                        view_radio = gr.Radio(
                            choices=["원문", "교정"],
                            value="원문",
                            label=None,
                            show_label=False,
                            interactive=True,
                            elem_classes="wn-view-radio",
                        )
                    text_display = gr.Textbox(
                        lines=13,
                        interactive=False,
                        show_label=False,
                        show_copy_button=True,
                        placeholder="[SPEAKER_00] [0.0s - 4.2s] 전사 결과가 여기에 표시됩니다...",
                        elem_classes="wn-result",
                    )
                    with gr.Row():
                        display_file_path = gr.Textbox(
                            interactive=False,
                            show_label=False,
                            lines=1,
                            elem_classes="wn-filepath",
                            scale=5,
                        )
                        btn_open_display_folder = gr.Button("📂 폴더 열기", elem_classes="wn-btn-secondary", scale=1, min_width=90)

                    # 내부 상태 저장용 (숨김)
                    transcript_output    = gr.Textbox(visible=False)
                    transcript_file_path = gr.Textbox(visible=False)
                    correction_output    = gr.Textbox(visible=False)
                    corrected_file_path  = gr.Textbox(visible=False)

                    gr.HTML('<hr class="wn-divider"><div class="wn-label">요약 결과</div>')
                    summary_output = gr.Textbox(
                        lines=13,
                        interactive=False,
                        show_label=False,
                        show_copy_button=True,
                        placeholder="## 핵심 내용\n- ...\n\n## 액션아이템\n- ...",
                        elem_classes="wn-result",
                    )
                    with gr.Row():
                        summary_file_path = gr.Textbox(
                            interactive=False,
                            show_label=False,
                            lines=1,
                            elem_classes="wn-filepath",
                            scale=5,
                        )
                        btn_open_summary_folder = gr.Button("📂 폴더 열기", elem_classes="wn-btn-secondary", scale=1, min_width=90)

        chunk_poll_timer = gr.Timer(value=2, active=False)

        # ════════════════════════════════════════════════════════
        # Tab 2 : 설정 가이드
        # ════════════════════════════════════════════════════════
        with gr.TabItem("  설정  "):
            with gr.Column(elem_classes="wn-card"):
                gr.Markdown("""
## config.py 설정 항목

| 항목 | 기본값 | 설명 |
|---|---|---|
| `WHISPER_MODEL` | `large-v3-turbo` | tiny / base / small / medium / large-v3 / large-v3-turbo |
| `WHISPER_LANGUAGE` | `ko` | 전사 언어 코드 |
| `WHISPER_DEVICE` | `cuda` | `cuda` 또는 `cpu` |
| `OLLAMA_MODEL` | `exaone3.5:latest` | 기본 요약 모델 |
| `INPUT_SOURCE` | `microphone` | `microphone` 또는 `loopback` |
| `ENABLE_DIARIZATION` | `True` | 화자 분리 사용 여부 |
| `NUM_SPEAKERS` | `None` | None=자동 감지, 숫자=고정 |

## 입력 소스

| 설정 | 설명 |
|---|---|
| `microphone` | 기본 마이크 |
| `loopback` | 시스템 오디오 (Zoom / Teams 캡처) |

> **loopback**: Windows 사운드 설정 → 녹음 탭 → **Stereo Mix** 활성화 필요

## 오프라인 동작

- WhisperX `large-v3-turbo` 모델: 최초 실행 시 자동 다운로드 (~1.6 GB) 후 캐시
- resemblyzer 가중치: pip 패키지에 내장 — 별도 다운로드 없음
- Ollama: `ollama serve` + 모델 pull 후 완전 오프라인
- **이후 회사 내 인터넷 없이 완전 로컬 실행 가능**

## 빠른 시작

```bash
pip install -r requirements.txt
ollama serve
ollama pull exaone3.5:latest
python app.py
```
                """)

                gr.HTML('<hr class="wn-divider"><div class="wn-label">오디오 입력 장치 목록</div>')
                btn_list_devices    = gr.Button("장치 목록 조회", elem_classes="wn-btn-secondary")
                device_list_output  = gr.Textbox(
                    interactive=False, show_label=False, lines=6,
                    elem_classes="wn-result"
                )
                btn_list_devices.click(list_audio_devices, outputs=device_list_output)

    # ── 이벤트 연결 ──────────────────────────────────────────

    # 페이지 로드
    demo.load(lambda: gr.update(choices=get_input_device_choices(), value=-1), outputs=[input_device])
    demo.load(fn=None, js=_LEVEL_JS)
    demo.load(fn=None, js=_FILE_LIST_JS)
    demo.load(init_cat_ui, inputs=[cat_data], outputs=[cat_l1, cat1_radio])
    demo.load(lambda: gr.update(choices=prompts.list_summary_types()), outputs=[summary_type])

    # 분류 설정 패널 열기/닫기
    btn_cat_settings.click(cat_open_panel, outputs=[cat_panel])
    btn_cat_close.click(sync_dropdowns_on_close, inputs=[cat_data, cat_l1, cat_l2], outputs=[cat_panel, cat_l2, cat_l3])

    # 설정 패널 라디오 cascade
    _l1_out = [cat2_radio, cat3_radio, cat2_header, cat3_header, cat_l1, cat_l2, cat_l3, cat_path_display]
    cat1_radio.change(on_panel_l1, inputs=[cat_data, cat1_radio], outputs=_l1_out)

    _l2_out = [cat3_radio, cat3_header, cat_l2, cat_l3, cat_path_display]
    cat2_radio.change(on_panel_l2, inputs=[cat_data, cat1_radio, cat2_radio], outputs=_l2_out)

    cat3_radio.change(on_panel_l3, inputs=[cat_data, cat1_radio, cat2_radio, cat3_radio], outputs=[cat_l3, cat_path_display])

    # 메인 드롭다운 cascade
    cat_l1.change(on_l1_change, inputs=[cat_data, cat_l1], outputs=[cat_l2, cat_l3, cat_path_display])
    cat_l2.change(on_l2_change, inputs=[cat_data, cat_l1, cat_l2], outputs=[cat_l3, cat_path_display])
    cat_l3.change(on_l3_change, inputs=[cat_data, cat_l1, cat_l2, cat_l3], outputs=[cat_path_display])

    # 추가 버튼
    _add_out = [cat_edit_ctx, cat_input_row, cat_input, cat_panel_msg]
    btn_cat1_add.click(lambda ctx: cat_start_add(ctx, 1, None),        inputs=[cat_edit_ctx], outputs=_add_out)
    btn_cat2_add.click(lambda ctx, p: cat_start_add(ctx, 2, p),         inputs=[cat_edit_ctx, cat1_radio], outputs=_add_out)
    btn_cat3_add.click(lambda ctx, p: cat_start_add(ctx, 3, p),         inputs=[cat_edit_ctx, cat2_radio], outputs=_add_out)

    # 수정 버튼
    _edit_out = [cat_edit_ctx, cat_input_row, cat_input, cat_panel_msg]
    btn_cat1_edit.click(lambda d, c, i: cat_start_edit(d, c, 1, i), inputs=[cat_data, cat_edit_ctx, cat1_radio], outputs=_edit_out)
    btn_cat2_edit.click(lambda d, c, i: cat_start_edit(d, c, 2, i), inputs=[cat_data, cat_edit_ctx, cat2_radio], outputs=_edit_out)
    btn_cat3_edit.click(lambda d, c, i: cat_start_edit(d, c, 3, i), inputs=[cat_data, cat_edit_ctx, cat3_radio], outputs=_edit_out)

    # 확인/취소
    _confirm_out = [cat_data, cat_edit_ctx, cat1_radio, cat2_radio, cat3_radio, cat_input_row, cat_panel_msg]
    btn_cat_ok.click(cat_confirm, inputs=[cat_data, cat_edit_ctx, cat_input, cat_l1, cat_l2, cat_l3], outputs=_confirm_out)
    btn_cat_cancel.click(cat_cancel, inputs=[cat_edit_ctx], outputs=[cat_edit_ctx, cat_input_row, cat_panel_msg])

    # 삭제 버튼
    _del_out = [cat_data, cat1_radio, cat2_radio, cat3_radio, cat_panel_msg, cat_l1, cat_l2, cat_l3, cat_path_display]
    btn_cat1_del.click(lambda d, i, l1, l2, l3: cat_delete(d, 1, i, l1, l2, l3), inputs=[cat_data, cat1_radio, cat_l1, cat_l2, cat_l3], outputs=_del_out)
    btn_cat2_del.click(lambda d, i, l1, l2, l3: cat_delete(d, 2, i, l1, l2, l3), inputs=[cat_data, cat2_radio, cat_l1, cat_l2, cat_l3], outputs=_del_out)
    btn_cat3_del.click(lambda d, i, l1, l2, l3: cat_delete(d, 3, i, l1, l2, l3), inputs=[cat_data, cat3_radio, cat_l1, cat_l2, cat_l3], outputs=_del_out)

    # 입력 장치 변경 → 슬라이더 표시/숨김
    def _update_gain_sliders(device_idx):
        sys_vis = device_idx in (_WASAPI_AUTO, _MIX_AUTO)
        return gr.update(visible=True), gr.update(visible=sys_vis)

    input_device.change(
        _update_gain_sliders,
        inputs=[input_device],
        outputs=[mic_gain_slider, system_gain_slider],
    )

    # 슬라이더 실시간 게인 적용
    mic_gain_slider.change(lambda v: setattr(recorder, "mic_gain", v), inputs=[mic_gain_slider])
    system_gain_slider.change(lambda v: setattr(recorder, "system_gain", v), inputs=[system_gain_slider])

    # 녹음 (카테고리 + 자동분할 + 모델/요약구분 파라미터 추가)
    btn_start.click(
        handle_start_recording,
        inputs=[input_device, cat_data, cat_l1, cat_l2, cat_l3, chunk_minutes_input,
                ollama_model, summary_type],
        outputs=[btn_start, btn_stop, btn_pause, btn_test, record_status, recorded_file],
    ).then(lambda: gr.update(active=True), outputs=[chunk_poll_timer])
    btn_stop.click(
        handle_stop_recording,
        outputs=[btn_start, btn_stop, btn_pause, btn_test, record_status, recorded_file],
    )
    btn_pause.click(handle_pause_resume, outputs=[btn_pause, record_status])
    _poll_outputs = [
        record_status, recorded_file,
        transcript_output, transcript_file_path,
        correction_output, corrected_file_path,
        pipeline_status, queue_status,
        chunk_poll_timer,
        text_display, view_radio, display_file_path,
        summary_output, summary_file_path,
    ]
    chunk_poll_timer.tick(handle_chunk_poll, inputs=[view_radio], outputs=_poll_outputs)
    btn_test.click(handle_mic_test, inputs=[input_device], outputs=[btn_test, record_status])
    btn_refresh.click(refresh_ollama_models, outputs=[ollama_model, model_status])
    btn_open_folder.click(handle_open_folder, inputs=[recorded_file])
    btn_open_display_folder.click(handle_open_folder, inputs=[display_file_path])
    btn_open_summary_folder.click(handle_open_folder, inputs=[summary_file_path])

    # 전사/교정/요약/파이프라인 공통 입력
    _cat_inputs = [cat_data, cat_l1, cat_l2, cat_l3]

    # 분류 변경 시 파일 목록 자동 갱신
    for _cat_dd in [cat_l1, cat_l2, cat_l3]:
        _cat_dd.change(
            load_folder_file_list,
            inputs=_cat_inputs,
            outputs=[file_list_display, file_paths, file_count_label],
        )

    # 파일 목록
    btn_fl_reload.click(
        load_folder_file_list,
        inputs=_cat_inputs,
        outputs=[file_list_display, file_paths, file_count_label],
    )
    btn_fl_remove.click(
        handle_remove_selected,
        inputs=[selected_paths, file_paths],
        outputs=[file_list_display, file_paths, file_count_label, selected_paths],
    )
    uploaded_files_add.upload(
        handle_upload_files,
        inputs=[uploaded_files_add, file_paths],
        outputs=[file_list_display, file_paths, file_count_label],
    )
    selected_paths.change(
        _on_file_select,
        inputs=[selected_paths, file_paths],
        outputs=[audio_preview, file_count_label, uploaded_file],
    )

    # view_radio 전환: 숨겨진 상태에서 표시 텍스트/파일 경로 갱신
    def switch_view(choice, transcript, correction, t_file, c_file):
        if choice == "교정":
            return gr.update(value=correction), gr.update(value=c_file)
        return gr.update(value=transcript), gr.update(value=t_file)

    view_radio.change(
        switch_view,
        inputs=[view_radio, transcript_output, correction_output, transcript_file_path, corrected_file_path],
        outputs=[text_display, display_file_path],
    )

    # 전사/교정/요약/파이프라인
    btn_transcribe.click(
        handle_transcribe,
        inputs=[recorded_file, uploaded_file] + _cat_inputs,
        outputs=[transcript_output, transcript_file_path, merged_stem_state, pipeline_status,
                 text_display, display_file_path, view_radio, correction_output, corrected_file_path],
    ).then(
        handle_correct,
        inputs=[transcript_output, recorded_file, uploaded_file, ollama_model, merged_stem_state] + _cat_inputs,
        outputs=[correction_output, corrected_file_path, pipeline_status,
                 text_display, view_radio, display_file_path],
    ).then(
        handle_summarize,
        inputs=[correction_output, transcript_output, recorded_file, uploaded_file,
                ollama_model, merged_stem_state, summary_type] + _cat_inputs,
        outputs=[summary_output, summary_file_path, pipeline_status],
    )
    btn_pipeline.click(
        handle_pipeline,
        inputs=[recorded_file, uploaded_file, ollama_model, summary_type] + _cat_inputs,
        outputs=[transcript_output, transcript_file_path, summary_output, summary_file_path,
                 pipeline_status, merged_stem_state,
                 text_display, display_file_path, view_radio, correction_output, corrected_file_path],
    )
    btn_summarize.click(
        handle_summarize,
        inputs=[correction_output, transcript_output,
                recorded_file, uploaded_file, ollama_model, merged_stem_state, summary_type] + _cat_inputs,
        outputs=[summary_output, summary_file_path, pipeline_status],
    )


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def _start_heartbeat_watcher():
    import time as _t, threading as _th, os as _os

    _TIMEOUT = 30.0   # 폴링 없으면 종료 대기 시간 (초)
    _CHECK   = 5.0    # 감시 주기 (초)

    def _watch():
        while True:
            _t.sleep(_CHECK)
            if _t.monotonic() - _last_heartbeat < _TIMEOUT:
                continue
            # 타임아웃 — 녹음/처리 완료 대기
            if recorder.recording or auto_worker.is_busy():
                print("브라우저 연결 끊김 — 처리 완료 후 종료 예정...", flush=True)
                while recorder.recording or auto_worker.is_busy():
                    _t.sleep(2)
            print("WhisperNote 종료 (브라우저 탭 닫힘).", flush=True)
            _os._exit(0)

    _th.Thread(target=_watch, daemon=True, name="heartbeat-watcher").start()


if __name__ == "__main__":
    print("  서버 시작 중 (포트 7860)...", flush=True)
    _app, _, _ = demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=False,  # run.bat 에서 프록시 우회 플래그로 직접 실행
        show_api=False,
        prevent_thread_lock=True,
    )
    _app.get("/api/level")(_api_level)
    # _start_heartbeat_watcher()  # 백그라운드 탭 throttle 오탐 문제로 임시 비활성화
    demo.block_thread()
