"""handlers_files.py — 파일 목록 UI 헬퍼 및 이벤트 핸들러."""
import json
from pathlib import Path

from handlers.category import _out_dir
from lib.transcript_view import render_html


def _scan_audio_files(folder) -> list:
    """폴더에서 오디오 파일을 파일명 오름차순으로 반환."""
    if not folder or not Path(folder).exists():
        return []
    exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}
    return sorted(
        [str(f) for f in Path(folder).iterdir() if f.suffix.lower() in exts],
        key=lambda p: Path(p).name.lower(),
    )


def _render_file_list(paths: list) -> str:
    """파일 목록 HTML 렌더링."""
    if not paths:
        return '<div id="wn-file-list"><div class="wn-file-empty">파일 없음</div></div>'
    items = "".join(
        f'<div class="wn-file-item" data-path="{p}" title="{p}">'
        f'<span class="wn-file-name">{Path(p).name}</span>'
        f'</div>'
        for p in paths
    )
    return f'<div id="wn-file-list">{items}</div>'


def load_folder_file_list(cat_data_val, l1_id, l2_id, l3_id):
    """분류 폴더 기반 파일 목록 로드."""
    folder = _out_dir(cat_data_val, l1_id, l2_id, l3_id)
    paths = _scan_audio_files(folder)
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
    return _render_file_list(merged), merged, f"전체 {len(merged)}개"


def _find_associated_files(wav_path: str) -> dict:
    """wav 파일 기준으로 연관 전사/교정/요약 파일 탐색.
    통합본 우선, 없으면 파트별 병합.
    반환: {"transcript": (text, path), "correction": (text, path), "summary": (text, path)}
    """
    p = Path(wav_path)
    d = p.parent
    base = p.stem.split("_part")[0]

    def _load(f: Path) -> str:
        try:
            return f.read_text(encoding="utf-8")
        except Exception:
            return ""

    result = {"transcript": ("", ""), "correction": ("", ""), "summary": ("", "")}

    # 전사: 통합본 우선 → 없으면 파트별 병합
    combined_t = d / f"{base}_transcript.txt"
    if combined_t.exists():
        result["transcript"] = (_load(combined_t), str(combined_t))
    else:
        parts = sorted(d.glob(f"{base}_part*_transcript.txt"))
        if parts:
            result["transcript"] = (
                "\n\n".join(_load(pt) for pt in parts),
                str(parts[0]),
            )

    # 교정: 통합본 우선 → 없으면 파트별 병합
    combined_c = d / f"{base}_transcript_corrected.txt"
    if combined_c.exists():
        result["correction"] = (_load(combined_c), str(combined_c))
    else:
        parts = sorted(d.glob(f"{base}_part*_transcript_corrected.txt"))
        if parts:
            result["correction"] = (
                "\n\n".join(_load(pt) for pt in parts),
                str(parts[0]),
            )

    # 요약
    summary_f = d / f"{base}_summary.txt"
    if summary_f.exists():
        result["summary"] = (_load(summary_f), str(summary_f))

    return result


def handle_file_selection(selected_json: str, file_paths_val: list):
    """선택된 파일 경로 JSON -> Audio 로드 + 선택 카운트."""
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
    try:
        selected = set(json.loads(selected_json)) if selected_json else set()
    except Exception:
        selected = set()
    remaining = [p for p in file_paths_val if p not in selected]
    html = _render_file_list(remaining)
    count = f"전체 {len(remaining)}개" if remaining else ""
    return html, remaining, count, ""


def on_file_select(selected_json: str, file_paths_val: list):
    """파일 선택 → audio_preview + 연관 전사/교정/요약 파일 로드."""
    import gradio as gr
    try:
        selected = json.loads(selected_json) if selected_json else []
    except Exception:
        selected = []

    audio_val = selected[0] if selected else None
    count_html = (
        f'<span style="color:#818cf8;font-size:.82rem">{len(selected)}개 선택</span>'
        if selected else ""
    )

    t_text = t_path = c_text = c_path = s_text = s_path = ""
    display_text = display_path = ""
    view_val = gr.update()

    if audio_val:
        assoc = _find_associated_files(audio_val)
        t_text, t_path = assoc["transcript"]
        c_text, c_path = assoc["correction"]
        s_text, s_path = assoc["summary"]

        if c_text:
            display_text, display_path, view_val = c_text, c_path, "교정"
        elif t_text:
            display_text, display_path, view_val = t_text, t_path, "원문"

    return (
        audio_val, count_html, audio_val or "",
        t_text, t_path,
        c_text, c_path,
        s_text, s_path,
        render_html(display_text), view_val, display_path,
    )
