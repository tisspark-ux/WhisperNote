from pathlib import Path

from config import OUTPUTS_DIR, RECORDINGS_DIR


def _safe_name(name: str) -> str:
    """Windows/Linux 파일 시스템에 안전한 폴더명으로 변환."""
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip() or "_"


def get_session_dir(
    l1: str | None, l2: str | None, l3: str | None
) -> Path | None:
    """선택된 카테고리 레벨까지 경로 반환. 미선택 시 None."""
    parts = [_safe_name(p) for p in (l1, l2, l3) if p]
    if not parts:
        return None
    path = OUTPUTS_DIR
    for part in parts:
        path = path / part
    return path


def resolve_wav_dir(l1: str | None, l2: str | None, l3: str | None) -> Path:
    """WAV 저장 디렉토리. 카테고리 선택 시 outputs/…, 미선택 시 recordings/."""
    d = get_session_dir(l1, l2, l3)
    return d if d is not None else RECORDINGS_DIR


def resolve_out_dir(l1: str | None, l2: str | None, l3: str | None) -> Path:
    """전사/요약 저장 디렉토리. 카테고리 선택 시 outputs/…, 미선택 시 outputs/."""
    d = get_session_dir(l1, l2, l3)
    return d if d is not None else OUTPUTS_DIR
