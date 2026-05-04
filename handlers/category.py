"""handlers_category.py — 분류(카테고리) 패널 헬퍼 및 이벤트 핸들러."""
import sys
from pathlib import Path

import gradio as gr

import data.categories as cat_mod
import data.storage as storage
from data.state import load_last_category, save_last_category


# ── 헬퍼 ──────────────────────────────────────────────────

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


# ── 패널 열기/닫기 ──────────────────────────────────────────

def cat_open_panel():
    return gr.update(visible=True)


def cat_close_panel():
    return gr.update(visible=False)


# ── 설정 패널 radio cascade ──────────────────────────────────

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


def on_panel_l3(data, l1_id, l2_id, l3_id):
    l3_ch = _cat_choices(data, l2_id)
    return gr.update(choices=l3_ch, value=l3_id), _path_html(data, l1_id, l2_id, l3_id)


# ── 메인 드롭다운 cascade ──────────────────────────────────

def on_l1_change(data, l1_id):
    from handlers.files import load_folder_file_list
    # 앱 시작 시 demo.load가 cat_l1을 설정하면 이 핸들러가 연쇄 실행됨.
    # 저장된 상태의 l1과 일치하면 l2/l3도 복원 (초기화 복원 지원).
    state = load_last_category()
    if state.get("l1") == l1_id:
        l2_id = state.get("l2")
        l3_id = state.get("l3")
    else:
        l2_id = l3_id = None

    l2_ch = _cat_choices(data, l1_id)
    l2_ids = [i for _, i in l2_ch]
    if l2_id not in l2_ids:
        l2_id = l3_id = None

    if l2_id:
        l3_ch = _cat_choices(data, l2_id)
        l3_ids = [i for _, i in l3_ch]
        if l3_id not in l3_ids:
            l3_id = None
    else:
        l3_ch = []
        l3_id = None

    save_last_category(l1_id, l2_id, l3_id)
    file_html, file_paths, file_count = load_folder_file_list(data, l1_id, l2_id, l3_id)
    return (
        gr.update(choices=l2_ch, value=l2_id),
        gr.update(choices=l3_ch, value=l3_id),
        _path_html(data, l1_id, l2_id, l3_id),
        file_html, file_paths, file_count,
    )


def on_l2_change(data, l1_id, l2_id):
    from handlers.files import load_folder_file_list
    # on_l1_change가 l2를 복원할 때 이 핸들러가 연쇄 실행됨. l3도 복원.
    state = load_last_category()
    if state.get("l1") == l1_id and state.get("l2") == l2_id:
        l3_id = state.get("l3")
    else:
        l3_id = None

    l3_ch = _cat_choices(data, l2_id)
    l3_ids = [i for _, i in l3_ch]
    if l3_id not in l3_ids:
        l3_id = None

    save_last_category(l1_id, l2_id, l3_id)
    file_html, file_paths, file_count = load_folder_file_list(data, l1_id, l2_id, l3_id)
    return (
        gr.update(choices=l3_ch, value=l3_id),
        _path_html(data, l1_id, l2_id, l3_id),
        file_html, file_paths, file_count,
    )


def on_l3_change(data, l1_id, l2_id, l3_id):
    from handlers.files import load_folder_file_list
    save_last_category(l1_id, l2_id, l3_id)
    file_html, file_paths, file_count = load_folder_file_list(data, l1_id, l2_id, l3_id)
    return _path_html(data, l1_id, l2_id, l3_id), file_html, file_paths, file_count


# ── 추가 / 수정 / 삭제 ──────────────────────────────────────

def cat_start_add(ctx, col, parent_id=None):
    lbl = {1: "대분류 추가", 2: "중분류 추가", 3: "소분류 추가"}
    return (
        {"col": col, "action": "add", "item_id": "", "parent_id": parent_id},
        gr.update(visible=True),
        gr.update(value="", label=lbl[col]),
        "",
    )


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


def cat_cancel(ctx):
    return {"col": 0, "action": "", "item_id": "", "parent_id": None}, gr.update(visible=False), ""


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


def cat_delete(data, col, item_id, l1_id, l2_id, l3_id):
    if not item_id:
        return (
            data, gr.update(), gr.update(), gr.update(),
            "⚠ 삭제할 항목을 선택하세요.",
            gr.update(), gr.update(), gr.update(),
            _path_html(data, l1_id, l2_id, l3_id),
        )
    n = cat_mod.count_descendants(data, item_id)
    item_name = cat_mod.get_name(data, item_id)
    data = cat_mod.delete_item(data, item_id)
    cat_mod.save(data)
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


def init_cat_ui(data):
    ch = _cat_choices(data, None)
    return gr.update(choices=ch, value=None), gr.update(choices=ch, value=None)


def init_cat_with_last_state(data):
    """앱 시작 시 마지막 분류 복원 + 파일 목록 초기화.

    outputs (8):
      cat_l1, cat1_radio,
      cat_l2, cat_l3,
      cat_path_display,
      file_list_display, file_paths, file_count_label
    """
    from handlers.files import load_folder_file_list

    ch = _cat_choices(data, None)
    state = load_last_category()
    l1_id = state.get("l1")
    l2_id = state.get("l2")
    l3_id = state.get("l3")

    # 존재하는 항목인지 검증
    l1_ids = [i for _, i in ch]
    if l1_id not in l1_ids:
        l1_id = l2_id = l3_id = None

    if l1_id is not None:
        l2_ch = _cat_choices(data, l1_id)
        l2_ids = [i for _, i in l2_ch]
        if l2_id not in l2_ids:
            l2_id = l3_id = None
    else:
        l2_ch = []

    if l2_id is not None:
        l3_ch = _cat_choices(data, l2_id)
        l3_ids = [i for _, i in l3_ch]
        if l3_id not in l3_ids:
            l3_id = None
    else:
        l3_ch = []

    file_html, file_paths, file_count = load_folder_file_list(data, l1_id, l2_id, l3_id)

    return (
        gr.update(choices=ch, value=l1_id),
        gr.update(choices=ch, value=l1_id),
        gr.update(choices=l2_ch, value=l2_id),
        gr.update(choices=l3_ch, value=l3_id),
        _path_html(data, l1_id, l2_id, l3_id),
        file_html,
        file_paths,
        file_count,
    )


def sync_dropdowns_on_close(data, l1_id, l2_id):
    """패널 닫기 + 드롭다운 choices 재동기화 (cascade 순서 문제 방지)."""
    l2_ch = _cat_choices(data, l1_id)
    l3_ch = _cat_choices(data, l2_id)
    return gr.update(visible=False), gr.update(choices=l2_ch), gr.update(choices=l3_ch)


# ── 폴더 열기 ──────────────────────────────────────────────

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
