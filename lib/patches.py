"""patches.py — 앱 시작 시 가장 먼저 import 해야 하는 패치 모음.

Windows CMD Quick Edit 비활성화, HuggingFace/Torch 홈 경로 지정,
회사 프록시 우회, SSL 인증서 우회, Gradio 4.x 버그 패치.
이 모듈을 import 하면 패치가 즉시 적용된다.
"""
import os
import sys
from pathlib import Path

# Windows CMD Quick Edit Mode 비활성화
# Quick Edit가 켜져 있으면 창을 클릭하는 순간 프로세스가 일시정지됨
if sys.platform == "win32":
    try:
        import ctypes as _ct
        _k32 = _ct.windll.kernel32
        _h = _k32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        _m = _ct.c_ulong()
        _k32.GetConsoleMode(_h, _ct.byref(_m))
        _k32.SetConsoleMode(_h, (_m.value & ~0x0040) | 0x0080)  # clear ENABLE_QUICK_EDIT
    except Exception:
        pass

# WhisperX 모델 캐시를 프로젝트 루트 models/ 폴더로 지정
# lib/patches.py 는 lib/ 안에 있으므로 .parent.parent 로 프로젝트 루트 참조
_PROJECT_ROOT = Path(__file__).parent.parent
os.environ.setdefault("HF_HOME", str(_PROJECT_ROOT / "models"))
os.environ.setdefault("TORCH_HOME", str(_PROJECT_ROOT / "models"))
os.environ.setdefault("HF_HUB_DISABLE_SSL_VERIFICATION", "1")

# Windows: HuggingFace Hub 내부 symlink 생성에 관리자 권한 또는 개발자 모드 필요
# 권한 없을 때(WinError 1314) 하드링크 → 파일 복사 순으로 폴백
if sys.platform == "win32":
    import shutil as _shutil
    _orig_symlink = os.symlink
    def _safe_symlink(src, dst, target_is_directory=False, *, dir_fd=None):
        try:
            _orig_symlink(src, dst, target_is_directory=target_is_directory, dir_fd=dir_fd)
        except OSError:
            try:
                os.link(src, dst)
            except OSError:
                _shutil.copy2(src, dst)
    os.symlink = _safe_symlink

# 회사 프록시에서 localhost 제외
for _k in ("no_proxy", "NO_PROXY"):
    _cur = os.environ.get(_k, "")
    _add = "localhost,127.0.0.1,0.0.0.0"
    os.environ[_k] = f"{_cur},{_add}" if _cur else _add

# Windows: 127.0.0.1 을 시스템 프록시 예외 목록에 추가
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

print("  [1/3] 네트워크 라이브러리 로딩...", flush=True)

# 회사 프록시 SSL 인증서 우회
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests as _req
_orig_req = _req.Session.request
def _no_ssl_verify(self, method, url, **kwargs):
    kwargs.setdefault("verify", False)
    if any(x in str(url) for x in ("localhost", "127.0.0.1", "0.0.0.0")):
        kwargs["proxies"] = {"http": None, "https": None}
    return _orig_req(self, method, url, **kwargs)
_req.Session.request = _no_ssl_verify

print("  [2/3] Gradio 로딩...", flush=True)
import gradio  # noqa: F401 — 이후 app.py에서 다시 import 해도 캐시 사용

# Gradio 4.x bug: JSON Schema value가 True/False 일 때 크래시 패치
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

# Gradio의 localhost 접근 가능 여부 체크 함수 패치 (회사 프록시 대응)
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
