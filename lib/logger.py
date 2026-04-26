"""lib/logger.py — 앱 공유 로거."""
import logging
from pathlib import Path

_LOGS_DIR = Path(__file__).parent.parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

_handler = logging.FileHandler(
    _LOGS_DIR / "whispernote.log", encoding="utf-8", mode="a"
)
_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
