"""Whisper model file-only downloader.
Called by install.bat and install_whisper.bat.
Usage: python download_whisper.py [--log <path>]

Does NOT load the model into memory (no ctranslate2 init).
Writes all output to both console and log file when --log is given.
"""
import sys
import os
import ssl
import traceback
import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# SSL bypass — corporate proxy injects self-signed cert, same fix as app.py
# Must be applied before any network import (requests, urllib3, huggingface_hub)
# ---------------------------------------------------------------------------
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["HF_HUB_DISABLE_SSL_VERIFICATION"] = "1"  # huggingface_hub >= 0.23

ssl._create_default_https_context = ssl._create_unverified_context

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests
_orig_request = requests.Session.request
def _no_verify(self, method, url, **kwargs):
    kwargs["verify"] = False
    return _orig_request(self, method, url, **kwargs)
requests.Session.request = _no_verify


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
_log_path = None
_args = sys.argv[1:]
if "--log" in _args:
    _i = _args.index("--log")
    if _i + 1 < len(_args):
        _log_path = _args[_i + 1]


# ---------------------------------------------------------------------------
# Tee: write to both console and log file simultaneously
# ---------------------------------------------------------------------------
class _Tee:
    def __init__(self, console, fileobj):
        self._c = console
        self._f = fileobj

    def write(self, s):
        try:
            self._c.write(s)
            self._c.flush()
        except Exception:
            pass
        try:
            self._f.write(s)
            self._f.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self._c.flush()
        except Exception:
            pass
        try:
            self._f.flush()
        except Exception:
            pass


_log_file = None
if _log_path:
    _log_file = open(_log_path, "w", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.__stdout__, _log_file)
    sys.stderr = _Tee(sys.__stderr__, _log_file)


def _close_log():
    if _log_file:
        try:
            _log_file.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Diagnostic header
# ---------------------------------------------------------------------------
print("=" * 60)
print("  WhisperNote - Whisper Model Download")
print("=" * 60)
print(f"Time   : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Python : {sys.version.split()[0]}  ({sys.executable})")
print(f"CWD    : {os.getcwd()}")
print()

_dir = Path(__file__).parent
sys.path.insert(0, str(_dir))

try:
    from config import WHISPER_MODEL
    print(f"Model  : {WHISPER_MODEL}")
except Exception as e:
    print(f"[ERROR] Cannot import config.py: {e}", file=sys.stderr)
    _close_log()
    sys.exit(1)

try:
    import faster_whisper as _fw
    _fw_ver = getattr(_fw, "__version__", "unknown")
    print(f"faster-whisper: {_fw_ver}")
except ImportError:
    print("faster-whisper: NOT INSTALLED", file=sys.stderr)
    _close_log()
    sys.exit(1)

try:
    import huggingface_hub as _hfh
    print(f"huggingface-hub: {getattr(_hfh, '__version__', 'unknown')}")
except ImportError:
    print("huggingface-hub: not found (will try faster_whisper method only)")

print()

# ---------------------------------------------------------------------------
# Cache check
# ---------------------------------------------------------------------------
models_dir = _dir / "models"
models_dir.mkdir(exist_ok=True)

cached = any(models_dir.rglob("model.bin")) or any(
    models_dir.rglob("model.safetensors")
)
if cached:
    print(f"Already cached under models/ — skipping download.")
    _close_log()
    sys.exit(0)

print(f"Downloading '{WHISPER_MODEL}' to models/ ...")
print("(May take several minutes. Network speed determines duration.)")
print()

# ---------------------------------------------------------------------------
# Method 1: faster_whisper.utils.download_model  (download only, no load)
# ---------------------------------------------------------------------------
success = False

try:
    from faster_whisper.utils import download_model as _fw_download
    print("[Method 1] faster_whisper.utils.download_model")
    path = _fw_download(WHISPER_MODEL, output_dir=str(models_dir))
    print(f"Saved to : {path}")
    success = True
except (ImportError, AttributeError):
    print("[Method 1] Not available in this version — trying Method 2.")
except Exception:
    print("[Method 1] Failed:")
    traceback.print_exc()

# ---------------------------------------------------------------------------
# Method 2: huggingface_hub.snapshot_download  (download only, no load)
# ---------------------------------------------------------------------------
if not success:
    try:
        from huggingface_hub import snapshot_download as _hf_snap
        repo_id = f"Systran/faster-whisper-{WHISPER_MODEL}"
        dest = models_dir / WHISPER_MODEL
        print(f"[Method 2] huggingface_hub.snapshot_download")
        print(f"           repo : {repo_id}")
        print(f"           dest : {dest}")
        path = _hf_snap(repo_id, local_dir=str(dest))
        print(f"Saved to : {path}")
        success = True
    except Exception:
        print("[Method 2] Failed:")
        traceback.print_exc()

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
print()
if success:
    print("=" * 60)
    print("  Download complete.")
    print("=" * 60)
    _close_log()
    sys.exit(0)
else:
    print("=" * 60)
    print("  Download FAILED. See log for details.")
    print("=" * 60)
    _close_log()
    sys.exit(1)
