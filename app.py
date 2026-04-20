"""
WhisperNote – 회의 녹음 → 전사 → 요약 자동화
실행: python app.py
"""

import os
from pathlib import Path

# WhisperX 모델 캐시를 프로젝트 내 models/ 폴더로 지정 (HuggingFace 최초 다운 후 오프라인 동작)
os.environ.setdefault("HF_HOME", str(Path(__file__).parent / "models"))
os.environ.setdefault("TORCH_HOME", str(Path(__file__).parent / "models"))

# 회사 프록시에서 localhost 제외 (Gradio가 자기 서버에 연결할 수 있도록)
for _k in ("no_proxy", "NO_PROXY"):
    _cur = os.environ.get(_k, "")
    _add = "localhost,127.0.0.1,0.0.0.0"
    os.environ[_k] = f"{_cur},{_add}" if _cur else _add

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

import gradio as gr

# Gradio의 localhost 접근 가능 여부 체크 함수를 패치
# 회사 프록시가 localhost까지 차단하는 환경 대응
import gradio.networking as _gn
_orig_url_ok = _gn.url_ok
def _url_ok_patched(url: str) -> bool:
    if any(x in url for x in ("localhost", "127.0.0.1", "0.0.0.0")):
        return True
    return _orig_url_ok(url)
_gn.url_ok = _url_ok_patched

from config import OLLAMA_MODEL
from recorder import AudioRecorder
from summarizer import Summarizer
from transcriber import Transcriber

recorder   = AudioRecorder()
transcriber = Transcriber()
summarizer  = Summarizer()

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
"""

# ---------------------------------------------------------------------------
# 로직 함수
# ---------------------------------------------------------------------------

def handle_start_recording():
    file_path, msg = recorder.start()
    if file_path:
        return (
            gr.update(interactive=False),
            gr.update(interactive=True),
            msg,
            file_path,
        )
    return (gr.update(interactive=True), gr.update(interactive=False), msg, "")


def handle_stop_recording():
    file_path, msg = recorder.stop()
    return (
        gr.update(interactive=True),
        gr.update(interactive=False),
        msg,
        file_path or "",
    )


def _resolve_audio(recorded: str, uploaded: str | None) -> str | None:
    return recorded if recorded else uploaded


def handle_transcribe(recorded: str, uploaded: str | None, progress=gr.Progress()):
    audio = _resolve_audio(recorded, uploaded)
    if not audio:
        return "", "", "오디오 파일을 선택하거나 먼저 녹음하세요."
    try:
        progress(0.1, desc="전사 시작...")
        transcript, out_file = transcriber.transcribe(
            audio, on_progress=lambda m: progress(0.5, desc=m)
        )
        progress(1.0, desc="전사 완료!")
        return transcript, out_file, f"완료 — {Path(out_file).name}"
    except Exception as exc:
        return "", "", f"전사 실패: {exc}"


def handle_summarize(
    transcript: str,
    recorded: str,
    uploaded: str | None,
    model_name: str,
    progress=gr.Progress(),
):
    if not transcript:
        return "", "", "먼저 전사를 실행하세요."
    audio = _resolve_audio(recorded, uploaded)
    audio_stem = Path(audio).stem if audio else "output"
    try:
        progress(0.2, desc="Ollama 요약 중...")
        summary, out_file = summarizer.summarize(transcript, audio_stem, model=model_name)
        progress(1.0, desc="요약 완료!")
        return summary, out_file, f"완료 — {Path(out_file).name}"
    except Exception as exc:
        return "", "", f"요약 실패: {exc}"


def handle_pipeline(
    recorded: str,
    uploaded: str | None,
    model_name: str,
    progress=gr.Progress(),
):
    audio = _resolve_audio(recorded, uploaded)
    if not audio:
        return "", "", "", "", "오디오 파일을 선택하거나 먼저 녹음하세요."
    try:
        progress(0.05, desc="전사 시작...")
        transcript, t_file = transcriber.transcribe(
            audio, on_progress=lambda m: progress(0.35, desc=m)
        )
        if not transcript:
            return "", t_file, "", "", "전사 결과가 비어 있습니다."

        progress(0.7, desc="요약 중...")
        summary, s_file = summarizer.summarize(
            transcript, Path(audio).stem, model=model_name
        )
        progress(1.0, desc="완료!")
        return (
            transcript, t_file,
            summary,   s_file,
            f"완료 — {Path(t_file).name} / {Path(s_file).name}",
        )
    except Exception as exc:
        return "", "", "", "", f"실패: {exc}"


def refresh_ollama_models():
    models = summarizer.get_available_models()
    if not models:
        return gr.update(choices=[OLLAMA_MODEL], value=OLLAMA_MODEL), "Ollama 연결 실패"
    value = OLLAMA_MODEL if OLLAMA_MODEL in models else models[0]
    return gr.update(choices=models, value=value), f"모델 {len(models)}개"


def list_audio_devices():
    return recorder.list_devices()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

with gr.Blocks(css=CSS, title="WhisperNote") as demo:

    # ── 헤더 ──
    gr.HTML("""
    <div id="wn-header">
        <h1>WhisperNote</h1>
        <p>회의 녹음 &nbsp;·&nbsp; 화자 분리 &nbsp;·&nbsp; 전사 &nbsp;·&nbsp; 요약 &nbsp;—&nbsp; 완전 로컬</p>
    </div>
    """)

    with gr.Tabs(elem_classes="wn-tabs"):

        # ════════════════════════════════════════════════════════
        # Tab 1 : 메인
        # ════════════════════════════════════════════════════════
        with gr.TabItem("  Studio  "):
            with gr.Row(equal_height=False):

                # ── 왼쪽 컨트롤 패널 ──────────────────────────
                with gr.Column(scale=1, min_width=300, elem_classes="wn-card"):

                    # 녹음
                    gr.HTML('<div class="wn-label">녹음</div>')
                    with gr.Row():
                        btn_start = gr.Button("● 녹음 시작", elem_id="btn-start")
                        btn_stop  = gr.Button("■ 녹음 종료", elem_id="btn-stop", interactive=False)

                    record_status = gr.Textbox(
                        value="대기 중",
                        interactive=False,
                        show_label=False,
                        elem_id="record-status",
                        lines=1,
                    )
                    recorded_file = gr.Textbox(
                        interactive=False,
                        show_label=False,
                        placeholder="녹음 후 파일 경로 자동 표시",
                        elem_classes="wn-filepath",
                        lines=1,
                    )

                    gr.HTML('<hr class="wn-divider"><div class="wn-label">파일 업로드</div>')
                    uploaded_file = gr.Audio(
                        label="",
                        type="filepath",
                        elem_classes="wn-upload",
                    )

                    gr.HTML('<hr class="wn-divider"><div class="wn-label">Ollama 모델</div>')
                    with gr.Row():
                        ollama_model = gr.Dropdown(
                            choices=[OLLAMA_MODEL],
                            value=OLLAMA_MODEL,
                            allow_custom_value=True,
                            show_label=False,
                            elem_classes="wn-dropdown",
                            scale=3,
                        )
                        btn_refresh = gr.Button(
                            "↻", elem_classes="wn-btn-secondary", scale=1
                        )
                    model_status = gr.Textbox(
                        interactive=False,
                        show_label=False,
                        lines=1,
                        elem_classes="wn-filepath",
                    )

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

                    gr.HTML('<div class="wn-label" style="margin-top:.8rem">전사 결과</div>')
                    transcript_output = gr.Textbox(
                        lines=13,
                        interactive=False,
                        show_label=False,
                        show_copy_button=True,
                        placeholder="[SPEAKER_00] [0.0s - 4.2s] 전사 결과가 여기에 표시됩니다...",
                        elem_classes="wn-result",
                    )
                    transcript_file_path = gr.Textbox(
                        interactive=False,
                        show_label=False,
                        lines=1,
                        elem_classes="wn-filepath",
                    )

                    gr.HTML('<div class="wn-label" style="margin-top:1rem">요약 결과</div>')
                    summary_output = gr.Textbox(
                        lines=13,
                        interactive=False,
                        show_label=False,
                        show_copy_button=True,
                        placeholder="## 핵심 내용\n- ...\n\n## 액션아이템\n- ...",
                        elem_classes="wn-result",
                    )
                    summary_file_path = gr.Textbox(
                        interactive=False,
                        show_label=False,
                        lines=1,
                        elem_classes="wn-filepath",
                    )

        # ════════════════════════════════════════════════════════
        # Tab 2 : 설정 가이드
        # ════════════════════════════════════════════════════════
        with gr.TabItem("  설정  "):
            with gr.Column(elem_classes="wn-card"):
                gr.Markdown("""
## config.py 설정 항목

| 항목 | 기본값 | 설명 |
|---|---|---|
| `WHISPER_MODEL` | `large-v3` | tiny / base / small / medium / large-v3 |
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

- WhisperX `large-v3` 모델: 최초 실행 시 자동 다운로드 (~3 GB) 후 캐시
- resemblyzer 가중치: 최초 실행 시 자동 다운로드 (~17 MB) 후 캐시
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
    btn_start.click(
        handle_start_recording,
        outputs=[btn_start, btn_stop, record_status, recorded_file],
    )
    btn_stop.click(
        handle_stop_recording,
        outputs=[btn_start, btn_stop, record_status, recorded_file],
    )
    btn_refresh.click(
        refresh_ollama_models,
        outputs=[ollama_model, model_status],
    )
    btn_transcribe.click(
        handle_transcribe,
        inputs=[recorded_file, uploaded_file],
        outputs=[transcript_output, transcript_file_path, pipeline_status],
    )
    btn_pipeline.click(
        handle_pipeline,
        inputs=[recorded_file, uploaded_file, ollama_model],
        outputs=[transcript_output, transcript_file_path, summary_output, summary_file_path, pipeline_status],
    )
    btn_summarize.click(
        handle_summarize,
        inputs=[transcript_output, recorded_file, uploaded_file, ollama_model],
        outputs=[summary_output, summary_file_path, pipeline_status],
    )


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=True,
        show_api=False,
    )
