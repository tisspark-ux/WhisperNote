"""
WhisperNote – 회의 녹음 → 전사 → 요약 자동화
실행: python app.py
"""
import logging
import traceback
import sys
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

print("WhisperNote 시작 중...", flush=True)
import lib.patches  # OS/SSL/Gradio 패치 (가장 먼저 실행)

print("  [3/3] AI 라이브러리 로딩 중 (최초 실행 시 30초 이상 소요)...", flush=True)
import gradio as gr
from version import __version__
from lib.instances import recorder, LOOPBACK_AUTO, REMOTE_AUTO, WASAPI_AUTO, MIX_AUTO
from lib.worker import auto_worker
import data.categories as cat_mod
import data.prompts as prompts
from lib.styles import CSS
from handlers.recording import (handle_start_recording, handle_stop_recording,
    handle_pause_resume, handle_chunk_poll, handle_mic_test)
from handlers.category import (
    _col_header, _path_html, cat_open_panel,
    on_panel_l1, on_panel_l2, on_panel_l3,
    on_l1_change, on_l2_change, on_l3_change,
    cat_start_add, cat_start_edit, cat_cancel, cat_confirm, cat_delete,
    init_cat_ui, init_cat_with_last_state, sync_dropdowns_on_close, handle_open_folder)
from handlers.files import (_render_file_list, load_folder_file_list,
    handle_upload_files, handle_remove_selected, handle_clear_file_list,
    handle_file_selection, on_file_select)
from config import OLLAMA_MODEL, OUTPUTS_DIR
from handlers.ai import (handle_transcribe, handle_correct, handle_load_transcripts,
    handle_summarize, handle_pipeline, handle_file_list_process,
    refresh_ollama_models, list_audio_devices, get_input_device_choices)

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
  var selected = [];

  // document 에 위임 — Gradio가 #wn-file-list HTML 전체를 교체해도 리스너 유지
  document.addEventListener('click', function(e) {
    var item = e.target.closest('.wn-file-item');
    if (!item) return;
    var list = document.getElementById('wn-file-list');
    if (!list || !list.contains(item)) return;

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
    if (!tb) return;
    var setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    setter.call(tb, JSON.stringify(selected));
    tb.dispatchEvent(new Event('input', {bubbles: true}));
    tb.dispatchEvent(new Event('change', {bubbles: true}));
  });

  // document.body 감시 — #wn-file-list 교체 시 선택 초기화
  new MutationObserver(function(mutations) {
    for (var m of mutations) {
      for (var node of m.addedNodes) {
        if (node.nodeType !== 1) continue;
        if (node.id === 'wn-file-list' || (node.querySelector && node.querySelector('#wn-file-list'))) {
          selected = [];
          return;
        }
      }
    }
  }).observe(document.body, {childList: true, subtree: true});
}"""

_TRANSCRIPT_JS = """() => {
  function wnSeekAudio(seconds) {
    var audio = document.getElementById('wn-audio-player');
    if (!audio) return;
    var wasPlaying = !audio.paused;
    audio.currentTime = seconds;
    if (wasPlaying) audio.play();
  }

  function wnTrUpdateCount(wrap) {
    var sel = wrap.querySelectorAll('.wn-tr-row.wn-selected').length;
    var total = wrap.querySelectorAll('.wn-tr-row').length;
    var cnt = wrap.querySelector('.wn-tr-count');
    if (cnt) cnt.textContent = sel > 0 ? sel + '개 선택 / ' + total + '개' : total + '개 세그먼트';
  }

  function wnTrCopy(btn) {
    var wrap = btn ? btn.closest('.wn-tr-wrap') : document.querySelector('.wn-tr-wrap');
    if (!wrap) return;
    var sel = wrap.querySelectorAll('.wn-tr-row.wn-selected');
    if (!sel.length) sel = wrap.querySelectorAll('.wn-tr-row');
    var lines = [];
    sel.forEach(function(row) {
      var time = row.querySelector('.wn-tr-time');
      var speaker = row.querySelector('.wn-tr-speaker');
      var text = row.querySelector('.wn-tr-text');
      var line = '';
      if (time && time.textContent.trim()) line += '[' + time.textContent.trim() + '] ';
      if (speaker && speaker.textContent.trim()) line += '[' + speaker.textContent.trim() + '] ';
      if (text) line += text.textContent.trim();
      if (line.trim()) lines.push(line);
    });
    if (navigator.clipboard) navigator.clipboard.writeText(lines.join('\\n')).catch(function() {});
  }

  document.addEventListener('click', function(e) {
    var copyBtn = e.target.closest('.wn-tr-copy-btn');
    if (copyBtn) { wnTrCopy(copyBtn); return; }

    var row = e.target.closest('.wn-tr-row');
    if (!row || row.classList.contains('wn-tr-row-plain')) return;

    var wrap = row.closest('.wn-tr-wrap');
    if (!wrap) return;

    if (e.shiftKey && wrap._wnLast) {
      var rows = Array.from(wrap.querySelectorAll('.wn-tr-row:not(.wn-tr-row-plain)'));
      var a = rows.indexOf(wrap._wnLast), b = rows.indexOf(row);
      if (a < 0) a = 0;
      var s = Math.min(a, b), eIdx = Math.max(a, b);
      rows.forEach(function(r, i) {
        if (i >= s && i <= eIdx) r.classList.add('wn-selected');
        else r.classList.remove('wn-selected');
      });
    } else if (e.ctrlKey || e.metaKey) {
      row.classList.toggle('wn-selected');
    } else {
      wrap.querySelectorAll('.wn-tr-row.wn-selected').forEach(function(r) { r.classList.remove('wn-selected'); });
      row.classList.add('wn-selected');
      var t = parseFloat(row.dataset.start);
      if (!isNaN(t)) wnSeekAudio(t);
    }
    if (!e.shiftKey) wrap._wnLast = row;
    wnTrUpdateCount(wrap);
  });
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
                    num_speakers_dd = gr.Dropdown(
                        label="화자 수",
                        choices=["자동", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                        value="자동",
                        interactive=True,
                        elem_classes="wn-dropdown",
                        scale=1,
                    )
                    summary_type = gr.Dropdown(
                        label="요약 구분",
                        choices=prompts.list_summary_types(),
                        value="면담",
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
                        btn_fl_add    = gr.UploadButton("＋",
                            file_types=[".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"],
                            file_count="multiple",
                            elem_classes="wn-btn-secondary",
                            scale=0, min_width=34,
                        )
                        btn_fl_remove = gr.Button("－", elem_classes="wn-btn-secondary wn-btn-del", scale=0, min_width=34)
                    file_list_display = gr.HTML(_render_file_list([]))
                    selected_paths = gr.Textbox(
                        elem_id="wn-selected-paths",
                        show_label=False,
                        elem_classes="wn-hidden-input",
                        lines=1,
                    )
                    audio_preview = gr.HTML(
                        value='<audio id="wn-audio-player" controls style="width:100%;outline:none;border-radius:6px"></audio>',
                        label="재생",
                        elem_id="wn-audio-preview",
                    )
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

                # ── 오른쪽 결과 패널 ──────────────────────────
                with gr.Column(scale=2, elem_classes="wn-card"):

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
                    text_display = gr.HTML(value="")
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
    demo.load(fn=None, js=_TRANSCRIPT_JS)
    demo.load(
        init_cat_with_last_state,
        inputs=[cat_data],
        outputs=[cat_l1, cat1_radio, cat_l2, cat_l3, cat_path_display,
                 file_list_display, file_paths, file_count_label],
    )
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
    cat_l1.change(on_l1_change, inputs=[cat_data, cat_l1],
                  outputs=[cat_l2, cat_l3, cat_path_display, file_list_display, file_paths, file_count_label])
    cat_l2.change(on_l2_change, inputs=[cat_data, cat_l1, cat_l2],
                  outputs=[cat_l3, cat_path_display, file_list_display, file_paths, file_count_label])
    cat_l3.change(on_l3_change, inputs=[cat_data, cat_l1, cat_l2, cat_l3],
                  outputs=[cat_path_display, file_list_display, file_paths, file_count_label])

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
        sys_vis = device_idx in (WASAPI_AUTO, MIX_AUTO)
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
                ollama_model, summary_type, num_speakers_dd],
        outputs=[btn_start, btn_stop, btn_pause, btn_test, record_status, recorded_file],
    ).then(lambda: gr.update(active=True), outputs=[chunk_poll_timer])
    btn_stop.click(
        handle_stop_recording,
        outputs=[btn_start, btn_stop, btn_pause, btn_test, record_status, recorded_file, audio_preview],
    ).then(
        load_folder_file_list,
        inputs=[cat_data, cat_l1, cat_l2, cat_l3],
        outputs=[file_list_display, file_paths, file_count_label],
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
    chunk_poll_timer.tick(
        handle_chunk_poll,
        inputs=[view_radio],
        outputs=_poll_outputs,
    )
    btn_test.click(handle_mic_test, inputs=[input_device], outputs=[btn_test, record_status])
    btn_refresh.click(refresh_ollama_models, outputs=[ollama_model, model_status])
    btn_open_folder.click(handle_open_folder, inputs=[recorded_file])
    btn_open_display_folder.click(handle_open_folder, inputs=[display_file_path])
    btn_open_summary_folder.click(handle_open_folder, inputs=[summary_file_path])

    # 전사/교정/요약/파이프라인 공통 입력
    _cat_inputs = [cat_data, cat_l1, cat_l2, cat_l3]

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
    btn_fl_add.upload(
        handle_upload_files,
        inputs=[btn_fl_add, file_paths],
        outputs=[file_list_display, file_paths, file_count_label],
    )
    selected_paths.change(
        on_file_select,
        inputs=[selected_paths, file_paths],
        outputs=[
            audio_preview, file_count_label, uploaded_file,
            transcript_output, transcript_file_path,
            correction_output, corrected_file_path,
            summary_output, summary_file_path,
            text_display, view_radio, display_file_path,
        ],
    )

    # view_radio 전환: 숨겨진 상태에서 표시 텍스트/파일 경로 갱신
    from lib.transcript_view import render_html as _render_html

    def switch_view(choice, transcript, correction, t_file, c_file):
        if choice == "교정":
            return gr.update(value=_render_html(correction)), gr.update(value=c_file)
        return gr.update(value=_render_html(transcript)), gr.update(value=t_file)

    view_radio.change(
        switch_view,
        inputs=[view_radio, transcript_output, correction_output, transcript_file_path, corrected_file_path],
        outputs=[text_display, display_file_path],
    )

    # 전사/교정/요약/파이프라인
    btn_transcribe.click(
        handle_transcribe,
        inputs=[recorded_file, uploaded_file] + _cat_inputs + [num_speakers_dd],
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
    def _fl_pipeline(sel, fps, model, stype, cat, l1, l2, l3, ns, rec, up,
                     progress=gr.Progress()):
        return handle_file_list_process(
            sel, fps, "pipeline", model, stype, cat, l1, l2, l3, ns, rec, up, progress)

    btn_pipeline.click(
        _fl_pipeline,
        inputs=[selected_paths, file_paths, ollama_model, summary_type]
               + _cat_inputs + [num_speakers_dd, recorded_file, uploaded_file],
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
        allowed_paths=[str(OUTPUTS_DIR.resolve().parent)],  # outputs 상위 폴더 전체 허용 → /file= 서빙
    )
    _app.get("/api/level")(_api_level)
    # _start_heartbeat_watcher()  # 백그라운드 탭 throttle 오탐 문제로 임시 비활성화
    demo.block_thread()
