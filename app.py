"""
WhisperNote – 회의 녹음 → 전사 → 요약 자동화
실행: python app.py
"""

from pathlib import Path

import gradio as gr

from config import OLLAMA_MODEL
from recorder import AudioRecorder
from summarizer import Summarizer
from transcriber import Transcriber

# 전역 인스턴스 (모델은 최초 사용 시 로드)
recorder = AudioRecorder()
transcriber = Transcriber()
summarizer = Summarizer()


# ===========================================================================
# 녹음
# ===========================================================================

def handle_start_recording():
    file_path, msg = recorder.start()
    if file_path:
        return (
            gr.update(interactive=False),   # btn_start
            gr.update(interactive=True),    # btn_stop
            msg,                            # record_status
            file_path,                      # recorded_file
        )
    return (
        gr.update(interactive=True),
        gr.update(interactive=False),
        msg,
        "",
    )


def handle_stop_recording():
    file_path, msg = recorder.stop()
    return (
        gr.update(interactive=True),    # btn_start
        gr.update(interactive=False),   # btn_stop
        msg,                            # record_status
        file_path or "",                # recorded_file
    )


# ===========================================================================
# 오디오 소스 선택 헬퍼
# ===========================================================================

def _resolve_audio(recorded: str, uploaded: str | None) -> str | None:
    if recorded:
        return recorded
    return uploaded


# ===========================================================================
# 전사 단독 실행
# ===========================================================================

def handle_transcribe(recorded: str, uploaded: str | None, progress=gr.Progress()):
    audio = _resolve_audio(recorded, uploaded)
    if not audio:
        return "", "", "오디오 파일을 선택하거나 먼저 녹음하세요."

    try:
        status_msgs: list[str] = []

        def on_progress(msg: str):
            status_msgs.append(msg)
            progress(0.5, desc=msg)

        progress(0.1, desc="전사 시작...")
        transcript, out_file = transcriber.transcribe(audio, on_progress=on_progress)
        progress(1.0, desc="전사 완료!")
        return transcript, out_file, f"전사 완료: {Path(out_file).name}"

    except Exception as exc:
        return "", "", f"전사 실패: {exc}"


# ===========================================================================
# 요약 단독 실행
# ===========================================================================

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
        progress(0.2, desc="Ollama에 요약 요청 중...")
        summary, out_file = summarizer.summarize(transcript, audio_stem, model=model_name)
        progress(1.0, desc="요약 완료!")
        return summary, out_file, f"요약 완료: {Path(out_file).name}"

    except Exception as exc:
        return "", "", f"요약 실패: {exc}"


# ===========================================================================
# 전사 + 요약 파이프라인 (한 번에 실행)
# ===========================================================================

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
        # 1. 전사
        progress(0.05, desc="전사 시작...")

        def on_transcribe_progress(msg: str):
            progress(0.3, desc=msg)

        transcript, transcript_file = transcriber.transcribe(audio, on_progress=on_transcribe_progress)

        if not transcript:
            return "", transcript_file, "", "", "전사 결과가 비어 있습니다."

        # 2. 요약
        progress(0.7, desc="요약 중...")
        audio_stem = Path(audio).stem
        summary, summary_file = summarizer.summarize(transcript, audio_stem, model=model_name)

        progress(1.0, desc="완료!")
        return (
            transcript,
            transcript_file,
            summary,
            summary_file,
            f"완료: {Path(transcript_file).name} / {Path(summary_file).name}",
        )

    except Exception as exc:
        return "", "", "", "", f"파이프라인 실패: {exc}"


# ===========================================================================
# Ollama 모델 목록 새로고침
# ===========================================================================

def refresh_ollama_models():
    models = summarizer.get_available_models()
    if not models:
        return gr.update(choices=[OLLAMA_MODEL], value=OLLAMA_MODEL), "Ollama 연결 실패 (서버 미실행?)"
    value = OLLAMA_MODEL if OLLAMA_MODEL in models else models[0]
    return gr.update(choices=models, value=value), f"모델 {len(models)}개 로드됨"


# ===========================================================================
# 오디오 장치 목록 조회
# ===========================================================================

def list_audio_devices():
    return recorder.list_devices()


# ===========================================================================
# Gradio UI
# ===========================================================================

with gr.Blocks(title="WhisperNote", theme=gr.themes.Soft()) as demo:

    gr.Markdown(
        """
        # WhisperNote
        **회의 녹음 → 전사(WhisperX) → 요약(Ollama) 로컬 자동화**
        """
    )

    with gr.Tabs():

        # ----------------------------------------------------------------
        # Tab 1 : 녹음 & 처리
        # ----------------------------------------------------------------
        with gr.TabItem("녹음 & 처리"):
            with gr.Row():

                # 왼쪽 컬럼: 컨트롤
                with gr.Column(scale=1, min_width=320):

                    gr.Markdown("### 녹음")
                    with gr.Row():
                        btn_start = gr.Button("녹음 시작", variant="primary")
                        btn_stop  = gr.Button("녹음 종료", variant="stop", interactive=False)

                    record_status = gr.Textbox(label="녹음 상태", interactive=False, value="대기 중")
                    recorded_file = gr.Textbox(label="녹음 파일", interactive=False, placeholder="(녹음 후 자동 입력)")

                    gr.Markdown("### 직접 업로드")
                    uploaded_file = gr.Audio(label="WAV/MP3 파일 업로드", type="filepath")

                    gr.Markdown("### Ollama 모델")
                    with gr.Row():
                        ollama_model   = gr.Dropdown(
                            label="모델 선택",
                            choices=[OLLAMA_MODEL],
                            value=OLLAMA_MODEL,
                            allow_custom_value=True,
                        )
                        btn_refresh = gr.Button("새로고침", size="sm")
                    model_status = gr.Textbox(label="", interactive=False, lines=1)

                    gr.Markdown("### 실행")
                    with gr.Row():
                        btn_transcribe = gr.Button("전사만 실행", variant="secondary")
                        btn_pipeline   = gr.Button("전사 + 요약", variant="primary")

                    btn_summarize = gr.Button("요약만 실행 (전사 결과 필요)", variant="secondary")

                # 오른쪽 컬럼: 결과
                with gr.Column(scale=2):

                    pipeline_status = gr.Textbox(label="처리 상태", interactive=False)

                    with gr.Accordion("전사 결과", open=True):
                        transcript_output = gr.Textbox(
                            label="전사문",
                            lines=14,
                            interactive=False,
                            show_copy_button=True,
                        )
                        transcript_file_path = gr.Textbox(label="저장 위치", interactive=False)

                    with gr.Accordion("요약 결과", open=True):
                        summary_output = gr.Textbox(
                            label="요약",
                            lines=14,
                            interactive=False,
                            show_copy_button=True,
                        )
                        summary_file_path = gr.Textbox(label="저장 위치", interactive=False)

        # ----------------------------------------------------------------
        # Tab 2 : 설정 안내
        # ----------------------------------------------------------------
        with gr.TabItem("설정 안내"):
            gr.Markdown(
                """
                ## config.py 주요 설정

                | 항목 | 기본값 | 설명 |
                |---|---|---|
                | `WHISPER_MODEL` | `large-v3` | tiny / base / small / medium / large-v3 |
                | `WHISPER_LANGUAGE` | `ko` | 전사 언어 코드 |
                | `WHISPER_DEVICE` | `cuda` | `cuda` (GPU) 또는 `cpu` |
                | `OLLAMA_MODEL` | `exaone3.5:latest` | 기본 요약 모델 |
                | `INPUT_SOURCE` | `microphone` | `microphone` 또는 `loopback` |

                ## 입력 소스

                | 설정값 | 설명 |
                |---|---|
                | `microphone` | 기본 마이크 녹음 |
                | `loopback` | 시스템 오디오 캡처 (Zoom/Teams 등) |

                > **loopback 사용 시**: Windows 사운드 설정 → 녹음 탭 → **Stereo Mix** 활성화 필요

                ## 필수 설치

                ```bash
                pip install -r requirements.txt
                ```

                ## Ollama 실행

                ```bash
                ollama serve
                ollama pull exaone3.5:latest
                ```
                """
            )

            gr.Markdown("### 현재 오디오 입력 장치 목록")
            btn_list_devices = gr.Button("장치 목록 조회")
            device_list_output = gr.Textbox(label="입력 장치", lines=8, interactive=False)
            btn_list_devices.click(list_audio_devices, outputs=device_list_output)

    # -----------------------------------------------------------------------
    # 이벤트 연결
    # -----------------------------------------------------------------------

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


# ===========================================================================
# 진입점
# ===========================================================================

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=True,
    )
