"""handlers_files.py — 파일 목록 UI 헬퍼 및 이벤트 핸들러."""
import json
import re
from pathlib import Path

from handlers.category import _out_dir
from lib.transcript_view import render_html, audio_html, render_audio_map
from data.vocab import save_hotwords_from_csv


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


def _sec_to_hms(secs: float) -> str:
    """초를 HH:MM:SS 형식으로 변환."""
    s = max(0, int(secs))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _audio_duration(audio_dir: Path, base: str, part_n: int) -> float:
    """파트 오디오 파일에서 재생 시간(초)을 구한다. 실패 시 0.0 반환."""
    exts = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm")
    for ext in exts:
        for fmt in (f"{base}_part{part_n:02d}{ext}", f"{base}_part{part_n}{ext}"):
            af = audio_dir / fmt
            if af.exists():
                try:
                    import soundfile as _sf
                    return _sf.info(str(af)).duration
                except Exception:
                    return 0.0
    return 0.0


def _merge_parts_with_headers(parts: list[Path], audio_dir: Path, base: str) -> str:
    """파트 전사 파일들을 [파트 N - HH:MM:SS ~ HH:MM:SS] 헤더와 함께 병합.

    헤더가 있어야 render_html이 data-part 속성을 설정하고
    JS의 파트 오디오 전환(wnSeekAudio)이 동작한다.
    """
    merged: list[str] = []
    cumulative = 0.0
    for pt in parts:
        m = re.search(r"_part(\d+)_transcript", pt.name, re.IGNORECASE)
        part_n = int(m.group(1)) if m else (len(merged) + 1)
        duration = _audio_duration(audio_dir, base, part_n)
        start_hms = _sec_to_hms(cumulative)
        cumulative += duration
        end_hms = _sec_to_hms(cumulative)
        header = f"[파트 {part_n} - {start_hms} ~ {end_hms}]"
        try:
            body = pt.read_text(encoding="utf-8")
        except Exception:
            body = ""
        merged.append(header + "\n" + body)
    return "\n\n".join(merged)


def _find_associated_files(wav_path: str) -> dict:
    """wav 파일 기준으로 연관 전사/교정/요약 파일 탐색.
    통합본 우선, 없으면 파트별 병합 (파트 헤더 포함).
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

    # 전사: 통합본 우선 → 없으면 파트별 병합 (파트 헤더 포함)
    combined_t = d / f"{base}_transcript.txt"
    if combined_t.exists():
        result["transcript"] = (_load(combined_t), str(combined_t))
    else:
        parts = sorted(d.glob(f"{base}_part*_transcript.txt"))
        if parts:
            merged = _merge_parts_with_headers(parts, d, base)
            result["transcript"] = (merged, str(parts[0]))

    # 교정: 통합본 우선 → 없으면 파트별 병합 (파트 헤더 포함)
    combined_c = d / f"{base}_transcript_corrected.txt"
    if combined_c.exists():
        result["correction"] = (_load(combined_c), str(combined_c))
    else:
        parts = sorted(d.glob(f"{base}_part*_transcript_corrected.txt"))
        if parts:
            merged = _merge_parts_with_headers(parts, d, base)
            result["correction"] = (merged, str(parts[0]))

    # 요약
    summary_f = d / f"{base}_summary.txt"
    if summary_f.exists():
        result["summary"] = (_load(summary_f), str(summary_f))

    return result


def _build_part_audio_map(wav_path: str) -> dict:
    """wav 파일 기준으로 같은 베이스의 파트 오디오 파일 탐색.
    반환: {part_index: wav_path, ...}  — 파트가 없으면 빈 dict
    """
    p = Path(wav_path)
    d = p.parent
    base = p.stem.split("_part")[0]
    exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}
    part_map = {}
    for f in d.iterdir():
        if f.suffix.lower() not in exts:
            continue
        m = re.match(rf"^{re.escape(base)}_part(\d+)", f.stem, re.IGNORECASE)
        if m:
            part_map[int(m.group(1))] = str(f)
    return part_map


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

    part_map = {}
    if audio_val:
        assoc = _find_associated_files(audio_val)
        t_text, t_path = assoc["transcript"]
        c_text, c_path = assoc["correction"]
        s_text, s_path = assoc["summary"]

        if t_text:
            display_text, display_path, view_val = t_text, t_path, "원문"
        elif c_text:
            display_text, display_path, view_val = c_text, c_path, "교정"

        part_map = _build_part_audio_map(audio_val)

    now_playing = (
        f'<div id="wn-now-playing">{Path(audio_val).name}</div>'
        if audio_val else '<div id="wn-now-playing"></div>'
    )
    return (
        audio_html(audio_val or ""), count_html, audio_val or "",
        t_text, t_path,
        c_text, c_path,
        s_text, s_path,
        render_html(display_text), view_val, display_path,
        render_audio_map(part_map),
        now_playing,
    )


def handle_save_hotwords(csv_text: str) -> str:
    """UI hotwords 텍스트박스 → hotwords.txt 저장."""
    try:
        count = save_hotwords_from_csv(csv_text)
        return f'<span style="color:#6ee7b7;font-size:.82rem">✓ {count}개 저장됨</span>'
    except Exception as exc:
        return f'<span style="color:#f87171;font-size:.82rem">저장 실패: {exc}</span>'
