"""
WhisperNote – 회의 녹음 → 전사 → 요약 자동화
실행: python app.py
"""

import os
import sys
import logging
import traceback
from pathlib import Path

# 앱 실행 중 발생하는 에러를 파일로 기록 (창 닫혀도 로그 남음)
_LOG_PATH = Path(__file__).parent / "whispernote_error.log"
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
from recorder import AudioRecorder, is_loopback_device_name
from summarizer import Summarizer
from transcriber import Transcriber
import categories as cat_mod
import storage

_LOOPBACK_AUTO = -2

print(f"WhisperNote v{__version__}")

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
"""

# ---------------------------------------------------------------------------
# 로직 함수
# ---------------------------------------------------------------------------

def handle_start_recording(device_idx, cat_data_val, l1_id, l2_id, l3_id):
    if device_idx == _LOOPBACK_AUTO:
        loopback_idx, _ = recorder.find_loopback_device()
        if loopback_idx is None:
            msg = ("루프백 장치를 찾을 수 없습니다.\n"
                   "Windows 사운드 설정 → 녹음 탭 → 'Stereo Mix' 활성화 후 재시도하거나,\n"
                   "장치 목록에서 직접 루프백 장치를 선택하세요.")
            return (gr.update(interactive=True), gr.update(interactive=False),
                    gr.update(interactive=False, value="⏸ 일시정지"),
                    gr.update(interactive=True, value="마이크 테스트"), msg, "")
        device = loopback_idx
    elif device_idx is None or device_idx == -1:
        device = None
    else:
        device = int(device_idx)
    file_path, msg = recorder.start(device_override=device, output_dir=_wav_dir(cat_data_val, l1_id, l2_id, l3_id))
    if file_path:
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


def handle_mic_test(device_idx):
    """마이크 테스트 토글."""
    if recorder.testing:
        msg = recorder.stop_test()
        return gr.update(value="마이크 테스트"), msg
    else:
        if device_idx == _LOOPBACK_AUTO:
            loopback_idx, _ = recorder.find_loopback_device()
            device = loopback_idx
        elif device_idx is None or device_idx == -1:
            device = None
        else:
            device = int(device_idx)
        msg = recorder.start_test(device_override=device)
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
    l2_ch = _cat_choices(data, l1_id)
    l1n = cat_mod.get_name(data, l1_id)
    return (
        gr.update(choices=l2_ch, value=None),
        gr.update(choices=[], value=None),
        gr.update(value=_col_header(2, l1n)),
        gr.update(value=_col_header(3, None)),
        gr.update(value=l1_id),
        gr.update(choices=l2_ch, value=None),
        gr.update(choices=[], value=None),
        _path_html(data, l1_id, None, None),
    )

# L2 radio 선택 → L3 초기화, 헤더 갱신, 드롭다운 갱신
def on_panel_l2(data, l1_id, l2_id):
    l3_ch = _cat_choices(data, l2_id)
    l2n = cat_mod.get_name(data, l2_id)
    return (
        gr.update(choices=l3_ch, value=None),
        gr.update(value=_col_header(3, l2n)),
        gr.update(value=l2_id),
        gr.update(choices=l3_ch, value=None),
        _path_html(data, l1_id, l2_id, None),
    )

# L3 radio 선택 → 드롭다운 + 경로 갱신
def on_panel_l3(data, l1_id, l2_id, l3_id):
    return gr.update(value=l3_id), _path_html(data, l1_id, l2_id, l3_id)

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


def _resolve_audio(recorded: str, uploaded: str | None) -> str | None:
    return recorded if recorded else uploaded


def handle_transcribe(recorded: str, uploaded: str | None, cat_data_val, l1_id, l2_id, l3_id, progress=gr.Progress()):
    audio = _resolve_audio(recorded, uploaded)
    if not audio:
        return "", "", "오디오 파일을 선택하거나 먼저 녹음하세요."
    try:
        progress(0.1, desc="전사 시작...")
        transcript, out_file = transcriber.transcribe(
            audio,
            on_progress=lambda m: progress(0.5, desc=m),
            output_dir=_out_dir(cat_data_val, l1_id, l2_id, l3_id),
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
    cat_data_val, l1_id, l2_id, l3_id,
    progress=gr.Progress(),
):
    if not transcript:
        return "", "", "먼저 전사를 실행하세요."
    audio = _resolve_audio(recorded, uploaded)
    audio_stem = Path(audio).stem if audio else "output"
    try:
        progress(0.2, desc="Ollama 요약 중...")
        summary, out_file = summarizer.summarize(
            transcript, audio_stem, model=model_name,
            output_dir=_out_dir(cat_data_val, l1_id, l2_id, l3_id),
        )
        progress(1.0, desc="요약 완료!")
        return summary, out_file, f"완료 — {Path(out_file).name}"
    except Exception as exc:
        return "", "", f"요약 실패: {exc}"


def handle_pipeline(
    recorded: str,
    uploaded: str | None,
    model_name: str,
    cat_data_val, l1_id, l2_id, l3_id,
    progress=gr.Progress(),
):
    audio = _resolve_audio(recorded, uploaded)
    if not audio:
        return "", "", "", "", "오디오 파일을 선택하거나 먼저 녹음하세요."
    out_dir = _out_dir(cat_data_val, l1_id, l2_id, l3_id)
    try:
        progress(0.05, desc="전사 시작...")
        transcript, t_file = transcriber.transcribe(
            audio,
            on_progress=lambda m: progress(0.35, desc=m),
            output_dir=out_dir,
        )
        if not transcript:
            return "", t_file, "", "", "전사 결과가 비어 있습니다."
        progress(0.7, desc="요약 중...")
        summary, s_file = summarizer.summarize(
            transcript, Path(audio).stem, model=model_name, output_dir=out_dir,
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


def get_input_device_choices():
    """UI 드롭다운용 (레이블, 인덱스) 선택지 목록 반환."""
    import sounddevice as sd
    choices = [("자동 감지 (기본값)", -1), ("🔊 루프백 자동감지", _LOOPBACK_AUTO)]
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            tag = " [루프백]" if is_loopback_device_name(dev["name"]) else ""
            choices.append((f"[{i}] {dev['name']}{tag}", i))
    return choices


async def _api_level():
    """레벨 미터 데이터를 JSON으로 반환하는 FastAPI 핸들러."""
    if recorder.paused:
        return {"status": "paused"}
    if recorder.recording or recorder.testing:
        return {"status": "active", "level": recorder.get_level(), "testing": bool(recorder.testing)}
    return {"status": "idle"}


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
        var filled = Math.round(lv / 10);
        var bar = '█'.repeat(filled) + '░'.repeat(10 - filled);
        el.style.color = lv > 80 ? '#ef4444' : '#6ee7b7';
        el.innerHTML = (d.testing ? '테스트 ' : '') + bar + '&nbsp;' + Math.round(lv) + '%';
      } else {
        el.style.color = '#4b5563';
        el.textContent = '마이크 대기 중';
      }
    } catch(e) {}
  }, 200);
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

            with gr.Row(equal_height=False):

                # ── 왼쪽 컨트롤 패널 ──────────────────────────
                with gr.Column(scale=1, min_width=300, elem_classes="wn-card"):

                    # 분류
                    gr.HTML('<div class="wn-label">분류</div>')
                    with gr.Row():
                        cat_l1 = gr.Dropdown(label="대분류", choices=[], value=None, interactive=True, elem_classes="wn-dropdown", scale=3)
                        cat_l2 = gr.Dropdown(label="중분류", choices=[], value=None, interactive=True, elem_classes="wn-dropdown", scale=3)
                        cat_l3 = gr.Dropdown(label="소분류", choices=[], value=None, interactive=True, elem_classes="wn-dropdown", scale=3)
                        btn_cat_settings = gr.Button("⚙", elem_id="btn-cat-settings", scale=1, min_width=36)
                    cat_path_display = gr.HTML('<div class="wn-cat-path">분류 미선택</div>')

                    # 녹음
                    gr.HTML('<hr class="wn-divider"><div class="wn-label">녹음</div>')
                    input_device = gr.Dropdown(
                        label="입력 장치",
                        choices=[("자동 감지 (기본값)", -1)],
                        value=-1,
                        interactive=True,
                        elem_classes="wn-dropdown",
                    )
                    with gr.Row():
                        btn_start = gr.Button("● 녹음 시작", elem_id="btn-start")
                        btn_stop  = gr.Button("■ 녹음 종료", elem_id="btn-stop", interactive=False)
                    with gr.Row():
                        btn_pause = gr.Button("⏸ 일시정지", elem_classes="wn-btn-secondary", interactive=False, scale=1)
                        btn_test  = gr.Button("마이크 테스트", elem_classes="wn-btn-secondary", scale=1)

                    level_display = gr.HTML(
                        value='<div id="wn-level-inner" class="wn-level-bar" style="color:#4b5563;height:36px;display:flex;align-items:center">마이크 대기 중</div>',
                        elem_id="wn-level-wrap",
                    )
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
    demo.load(init_cat_ui, inputs=[cat_data], outputs=[cat_l1, cat1_radio])

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

    # 녹음 (카테고리 파라미터 추가)
    btn_start.click(
        handle_start_recording,
        inputs=[input_device, cat_data, cat_l1, cat_l2, cat_l3],
        outputs=[btn_start, btn_stop, btn_pause, btn_test, record_status, recorded_file],
    )
    btn_stop.click(
        handle_stop_recording,
        outputs=[btn_start, btn_stop, btn_pause, btn_test, record_status, recorded_file],
    )
    btn_pause.click(handle_pause_resume, outputs=[btn_pause, record_status])
    btn_test.click(handle_mic_test, inputs=[input_device], outputs=[btn_test, record_status])
    btn_refresh.click(refresh_ollama_models, outputs=[ollama_model, model_status])

    # 전사/요약/파이프라인 (카테고리 파라미터 추가)
    _cat_inputs = [cat_data, cat_l1, cat_l2, cat_l3]
    btn_transcribe.click(
        handle_transcribe,
        inputs=[recorded_file, uploaded_file] + _cat_inputs,
        outputs=[transcript_output, transcript_file_path, pipeline_status],
    )
    btn_pipeline.click(
        handle_pipeline,
        inputs=[recorded_file, uploaded_file, ollama_model] + _cat_inputs,
        outputs=[transcript_output, transcript_file_path, summary_output, summary_file_path, pipeline_status],
    )
    btn_summarize.click(
        handle_summarize,
        inputs=[transcript_output, recorded_file, uploaded_file, ollama_model] + _cat_inputs,
        outputs=[summary_output, summary_file_path, pipeline_status],
    )


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

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
    demo.block_thread()
