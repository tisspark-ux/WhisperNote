import json
import uuid

from config import CATEGORIES_FILE


def load() -> list[dict]:
    if not CATEGORIES_FILE.exists():
        return []
    try:
        return json.loads(CATEGORIES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save(data: list[dict]) -> None:
    CATEGORIES_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _find(nodes: list[dict], item_id: str) -> dict | None:
    for node in nodes:
        if node["id"] == item_id:
            return node
        found = _find(node.get("children", []), item_id)
        if found:
            return found
    return None


def get_level_items(data: list[dict], parent_id: str | None) -> list[dict]:
    """parent_id=None → 1단계 목록, parent_id=X → X의 자식 목록."""
    if parent_id is None:
        return data
    parent = _find(data, parent_id)
    return parent.get("children", []) if parent else []


def add_item(data: list[dict], name: str, parent_id: str | None) -> list[dict]:
    new_item = {"id": str(uuid.uuid4()), "name": name.strip(), "children": []}
    if parent_id is None:
        data.append(new_item)
    else:
        parent = _find(data, parent_id)
        if parent is not None:
            parent.setdefault("children", []).append(new_item)
    return data


def rename_item(data: list[dict], item_id: str, new_name: str) -> list[dict]:
    item = _find(data, item_id)
    if item:
        item["name"] = new_name.strip()
    return data


def delete_item(data: list[dict], item_id: str) -> list[dict]:
    data[:] = [i for i in data if i["id"] != item_id]
    for item in data:
        delete_item(item.get("children", []), item_id)
    return data


def get_name(data: list[dict], item_id: str | None) -> str | None:
    if not item_id:
        return None
    item = _find(data, item_id)
    return item["name"] if item else None


def count_descendants(data: list[dict], item_id: str) -> int:
    """항목의 모든 하위 항목 수 반환 (삭제 경고용)."""
    item = _find(data, item_id)
    if not item:
        return 0

    def _count(nodes: list[dict]) -> int:
        total = len(nodes)
        for n in nodes:
            total += _count(n.get("children", []))
        return total

    return _count(item.get("children", []))
