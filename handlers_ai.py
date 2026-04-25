"""handlers_ai.py — 전사/교정/요약/파이프라인 이벤트 핸들러."""
from pathlib import Path

import gradio as gr
import sounddevice as sd

from config import OLLAMA_MODEL
from instances import recorder, transcriber, summarizer, LOOPBACK_AUTO, REMOTE_AUTO, WASAPI_AUTO, MIX_AUTO
from recorder import is_loopback_device_name, is_rdp_device_name
from worker import auto_worker
from handlers_category import _out_dir
import prompts


def _resolve_audio(recorded: str, uploaded: str | None) -> str | None:
    return recorded if recorded else uploaded


# ── 전사 ──────────────────────────────────────────────────

def handle_transcribe(recorded: str, uploaded: str | None,
                      cat_data_val, l1_id, l2_id, l3_id,
                      progress=gr.Progress()):
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
        return (
            transcript, out_file, "", f"완료 — {Path(out_file).name}",
            gr.update(value=transcript), gr.update(value=out_file),
            gr.update(value="원문"), gr.update(value=""), gr.update(value=""),
        )
    except Exception as exc:
        return "", "", "", f"전사 실패: {exc}", *_no


# ── 교정 ──────────────────────────────────────────────────

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
        return (
            corrected, out_file, f"완료 — {Path(out_file).name}",
            gr.update(value=corrected), gr.update(value="교정"), gr.update(value=out_file),
        )
    except Exception as exc:
        return "", "", f"교정 실패: {exc}", *_no


# ── 전사 파일 병합 ─────────────────────────────────────────

def handle_load_transcripts(files):
    _no = (gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
    if not files:
        return "", "", "전사 파일을 선택하세요.", *_no
    sorted_files = sorted(files, key=lambda f: Path(f).name)
    parts = [Path(f).read_text(encoding="utf-8") for f in sorted_files]
    merged = "\n\n".join(parts)
    first_stem = Path(sorted_files[0]).stem.replace("_transcript", "")
    merged_stem = f"{first_stem}_merged"
    return (
        merged, merged_stem, f"전사 파일 {len(sorted_files)}개 병합 완료",
        gr.update(value=merged), gr.update(value=""), gr.update(value="원문"),
        gr.update(value=""), gr.update(value=""),
    )


# ── 요약 ──────────────────────────────────────────────────

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


# ── 통합 파이프라인 ────────────────────────────────────────

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
            corrected_text, audio_stem, model=model_name,
            output_dir=out_dir, summary_type=summary_type_val,
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


# ── 파일 목록 일괄 처리 ────────────────────────────────────

def handle_file_list_process(
    selected_json: str,
    file_paths: list,
    action: str,
    model_name: str,
    summary_type_val: str,
    cat_data_val, l1_id, l2_id, l3_id,
    progress=gr.Progress(),
):
    """파일 목록에서 선택된 파일 처리. outputs: 11개."""
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
            return handle_pipeline(audio, None, model_name, summary_type_val,
                                   cat_data_val, l1_id, l2_id, l3_id, progress)
        elif action == "transcribe":
            res = handle_transcribe(audio, None, cat_data_val, l1_id, l2_id, l3_id, progress)
            return (
                res[0], res[1],
                gr.update(), gr.update(),
                res[3], res[2],
                res[4], res[5], res[6], res[7], res[8],
            )
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
        return *_no11[:10], f"처리 시작 - {len(selected)}개 파일"


# ── Ollama 모델 ────────────────────────────────────────────

def refresh_ollama_models():
    models = summarizer.get_available_models()
    if not models:
        return (
            gr.update(choices=[OLLAMA_MODEL], value=OLLAMA_MODEL),
            '<div class="wn-cat-path" style="color:#ef4444">⚠ Ollama 연결 실패 — ollama serve 실행 여부 확인</div>',
        )
    value = OLLAMA_MODEL if OLLAMA_MODEL in models else models[0]
    return gr.update(choices=models, value=value), ""


# ── 오디오 장치 ────────────────────────────────────────────

def list_audio_devices():
    return recorder.list_devices()


def get_input_device_choices():
    """UI 드롭다운용 (레이블, 인덱스) 선택지 목록 반환."""
    choices = [
        ("(PC) 🎙 대면회의",     -1),
        ("(PC) 🎙+🎧 원격회의",  WASAPI_AUTO),
        ("(원격) 🖥 대면회의",   REMOTE_AUTO),
        ("(원격) 🎙+🎧 원격회의", MIX_AUTO),
    ]
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            tag = " [루프백]" if is_loopback_device_name(dev["name"]) else (
                " [원격]" if is_rdp_device_name(dev["name"]) else ""
            )
            choices.append((f"[{i}] {dev['name']}{tag}", i))
    return choices
