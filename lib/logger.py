"""lib/logger.py — 앱 공유 로거 (날짜별 파일)."""
import logging
from datetime import datetime
from pathlib import Path

_LOGS_DIR = Path(__file__).parent.parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

_today = datetime.now().strftime("%Y-%m-%d")
_handler = logging.FileHandler(
    _LOGS_DIR / f"whispernote_{_today}.log", encoding="utf-8", mode="a"
)
_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
