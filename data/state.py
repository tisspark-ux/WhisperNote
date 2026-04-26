"""data/state.py — 앱 상태 영속화 (last_state.json)."""
import json
from pathlib import Path

_STATE_FILE = Path(__file__).parent.parent / "last_state.json"


def load_last_category() -> dict:
    """마지막 선택 분류 반환. 파일 없거나 오류 시 빈 dict."""
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_last_category(l1_id, l2_id, l3_id):
    """마지막 선택 분류를 파일에 저장."""
    try:
        _STATE_FILE.write_text(
            json.dumps({"l1": l1_id, "l2": l2_id, "l3": l3_id}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass
