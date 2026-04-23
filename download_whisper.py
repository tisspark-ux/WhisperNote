"""install.bat 에서 Whisper 모델 파일만 사전 다운로드하는 헬퍼.
WhisperModel() 생성자는 다운로드 + 메모리 로드를 동시에 수행하므로
설치 시점에 호출하면 RAM 부족 / ctranslate2 초기화 오류가 발생할 수 있다.
이 스크립트는 파일 다운로드만 수행하고 로드는 하지 않는다.
"""
import sys
from pathlib import Path

_dir = Path(__file__).parent
sys.path.insert(0, str(_dir))

from config import WHISPER_MODEL

models_dir = _dir / "models"
models_dir.mkdir(exist_ok=True)

cached = (
    any(models_dir.rglob("model.bin"))
    or any(models_dir.rglob("model.safetensors"))
)
if cached:
    print(f"Whisper '{WHISPER_MODEL}' already cached, skipping.")
    sys.exit(0)

print(f"Downloading '{WHISPER_MODEL}' model files (no loading)...")

try:
    from faster_whisper.utils import download_model
    path = download_model(WHISPER_MODEL, output_dir=str(models_dir))
    print(f"Model saved: {path}")
    sys.exit(0)
except (ImportError, AttributeError):
    pass
except Exception as e:
    print(f"[ERROR] faster_whisper download_model failed: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from huggingface_hub import snapshot_download
    repo_id = f"Systran/faster-whisper-{WHISPER_MODEL}"
    path = snapshot_download(repo_id, local_dir=str(models_dir / WHISPER_MODEL))
    print(f"Model saved: {path}")
    sys.exit(0)
except Exception as e:
    print(f"[ERROR] huggingface_hub download failed: {e}", file=sys.stderr)
    sys.exit(1)
