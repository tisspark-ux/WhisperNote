"""PyTorch GPU/CPU 선택 설치 스크립트."""
import os
import re
import subprocess
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_SCRIPTS = os.path.dirname(sys.executable)
_PIP_EXE = os.path.join(_SCRIPTS, "pip.exe")
_PIP = [_PIP_EXE] if os.path.exists(_PIP_EXE) else [sys.executable, "-m", "pip"]

_TORCH_PKGS = ["torch", "torchvision", "torchaudio"]
_COMMON = [
    "--no-cache-dir",
    "--trusted-host", "download.pytorch.org",
    "--trusted-host", "files.pythonhosted.org",
    "--trusted-host", "pypi.org",
]
_CPU_INDEX = "https://download.pytorch.org/whl/cpu"

# (최소 드라이버 CUDA 버전, 태그, 설치되는 CUDA 버전, 인덱스URL)
_CUDA_BUILDS = [
    (12.4, "cu124", "12.4", "https://download.pytorch.org/whl/cu124"),
    (12.1, "cu121", "12.1", "https://download.pytorch.org/whl/cu121"),
    (11.8, "cu118", "11.8", "https://download.pytorch.org/whl/cu118"),
]


def _detect_gpus():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, timeout=5,
        )
        if r.returncode == 0:
            out = r.stdout.decode("utf-8", errors="replace")
            return [g.strip() for g in out.strip().splitlines() if g.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return []


def _detect_driver_cuda_version():
    """nvidia-smi 에서 드라이버가 지원하는 최대 CUDA 버전 반환. 실패 시 None."""
    for cmd in [["nvidia-smi"], ["nvidia-smi", "-q"]]:
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=10)
            if r.returncode == 0:
                out = r.stdout.decode("utf-8", errors="replace")
                m = re.search(r"CUDA Version\s*[:\s]+(\d+)\.(\d+)", out)
                if m:
                    return float(f"{m.group(1)}.{m.group(2)}")
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
    return None


def _select_cuda_build(driver_cuda_ver):
    """드라이버 CUDA 버전에 맞는 (태그, cuda버전, URL) 반환. 미지원이면 None."""
    for min_ver, tag, cuda_ver, url in _CUDA_BUILDS:
        if driver_cuda_ver >= min_ver:
            return tag, cuda_ver, url
    return None


def _installed_type():
    r = subprocess.run(
        [sys.executable, "-c",
         "import torch; "
         "cuda=torch.version.cuda; "
         "print('cuda' if cuda and cuda != 'None' else 'cpu')"],
        capture_output=True, text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else None


def _cuda_ok():
    r = subprocess.run(
        [sys.executable, "-c",
         "import torch; exit(0 if torch.cuda.is_available() else 1)"],
        capture_output=True,
    )
    return r.returncode == 0


def _torch_info():
    """(torch버전, torch.version.cuda 또는 None) 반환."""
    r = subprocess.run(
        [sys.executable, "-c",
         "import torch; "
         "cuda=torch.version.cuda; "
         "print(torch.__version__); "
         "print(cuda if cuda and cuda != 'None' else '')"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        lines = r.stdout.strip().splitlines()
        ver = lines[0] if lines else "?"
        cuda_ver = lines[1] if len(lines) > 1 and lines[1] else None
        return ver, cuda_ver
    return "?", None


def _print_installed_info():
    ver, cuda_ver = _torch_info()
    if cuda_ver:
        avail = "GPU 사용 가능" if _cuda_ok() else "GPU 인식 불가"
        print(f"  [현재 설치] PyTorch {ver}  |  CUDA {cuda_ver}  |  {avail}")
    else:
        print(f"  [현재 설치] PyTorch {ver}  |  CPU 전용 빌드")


def _uninstall():
    print("  기존 PyTorch 제거 중...")
    subprocess.run(
        _PIP + ["uninstall", "-y"] + _TORCH_PKGS,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _install(index_url: str, label: str) -> bool:
    print(f"  PyTorch {label} 설치 중 (수 분 소요)...")
    r = subprocess.run(
        _PIP + ["install"] + _TORCH_PKGS + ["--index-url", index_url] + _COMMON
    )
    return r.returncode == 0


def _find_latest_cuda_version(cuda_tag: str, index_url: str) -> str | None:
    """pip index versions 으로 인덱스에서 최신 CUDA 빌드 버전 탐색."""
    try:
        r = subprocess.run(
            _PIP + ["index", "versions", "torch", "--index-url", index_url],
            capture_output=True, text=True, timeout=30,
        )
        # 출력 예: "torch (2.8.0+cpu, 2.7.0+cu124, 2.6.0+cu124, ...)"
        versions = re.findall(rf'(\d+\.\d+\.\d+\+{cuda_tag})', r.stdout)
        return versions[0] if versions else None
    except Exception:
        return None


def _install_pinned_cuda(cuda_tag: str, index_url: str) -> bool:
    """최신 버전에 CUDA 빌드 없을 때 인덱스에서 최신 CUDA 빌드 버전을 찾아 고정 설치."""
    print(f"  인덱스에서 최신 {cuda_tag} 빌드 버전 탐색 중...")
    ver = _find_latest_cuda_version(cuda_tag, index_url)
    if not ver:
        print(f"  [오류] {cuda_tag} 인덱스에서 CUDA 빌드를 찾지 못했습니다.")
        return False
    # torch/torchaudio는 버전 동일, torchvision은 pip가 호환 버전 자동 선택
    base = ver.split("+")[0]
    pkgs = [f"torch=={ver}", f"torchaudio=={base}+{cuda_tag}", "torchvision"]
    print(f"  PyTorch {ver} 고정 설치 중 (수 분 소요)...")
    r = subprocess.run(_PIP + ["install"] + pkgs + ["--index-url", index_url] + _COMMON)
    return r.returncode == 0


def _ask_cuda_manual():
    """CUDA 버전 감지 실패 시 수동 선택. (태그, cuda버전, URL) 또는 None(CPU) 반환."""
    print()
    print("  nvidia-smi 에서 CUDA 버전 감지 실패.")
    print("  nvidia-smi 실행 후 우측 상단 'CUDA Version: X.X' 를 확인하세요.")
    print()
    print("  설치할 버전을 선택하세요:")
    print("    1. GPU (cu124) - CUDA 12.4 이상 드라이버")
    print("    2. GPU (cu121) - CUDA 12.1 ~ 12.3 드라이버")
    print("    3. GPU (cu118) - CUDA 11.8 ~ 12.0 드라이버")
    print("    4. CPU 버전")
    choices = {
        "1": ("cu124", "12.4", "https://download.pytorch.org/whl/cu124"),
        "2": ("cu121", "12.1", "https://download.pytorch.org/whl/cu121"),
        "3": ("cu118", "11.8", "https://download.pytorch.org/whl/cu118"),
        "4": None,
    }
    while True:
        ans = input("  선택 (1~4): ").strip()
        if ans in choices:
            return choices[ans]
        print("  잘못된 입력입니다. 1~4 중 하나를 입력하세요.")


def main() -> int:
    gpus = _detect_gpus()
    driver_cuda = _detect_driver_cuda_version()
    installed = _installed_type()

    print()

    # GPU / CUDA 버전 출력
    if gpus:
        print("  [GPU 감지됨]")
        for g in gpus:
            print(f"    - {g}")
        if driver_cuda:
            print(f"  [드라이버 지원 CUDA] {driver_cuda:.1f}")
            build = _select_cuda_build(driver_cuda)
            if build:
                cuda_tag, cuda_ver, cuda_url = build
                print(f"  [권장 빌드] {cuda_tag}  (PyTorch CUDA {cuda_ver} 버전)")
            else:
                print("  [경고] 드라이버가 CUDA 11.8 미만 - PyTorch GPU 미지원")
                cuda_tag = cuda_ver = cuda_url = None
        else:
            cuda_tag = cuda_ver = cuda_url = None  # 감지 실패 → 수동 선택
        default_gpu = True
    else:
        print("  [NVIDIA GPU 없음 - CPU 버전 권장]")
        driver_cuda = None
        cuda_tag = cuda_ver = cuda_url = None
        default_gpu = False

    # 현재 설치 상태
    if installed:
        _print_installed_info()
        cuda_ok_now = (installed == "cuda" and _cuda_ok())
        cpu_ok_now  = (installed == "cpu")
    else:
        print("  [현재 설치] PyTorch 없음")
        cuda_ok_now = cpu_ok_now = False

    # ── 선택 분기 ──────────────────────────────────────────────

    if default_gpu and cuda_tag is None and driver_cuda is not None:
        # 드라이버 너무 구버전
        print()
        print("  설치할 버전을 선택하세요:")
        print("    1. CPU 버전  [권장]")
        print("    2. GPU 버전  (드라이버 업데이트 필요)")
        while True:
            ans = input("  선택 (1 또는 2): ").strip()
            if ans == "1":
                want_gpu = False
                break
            elif ans == "2":
                result = _ask_cuda_manual()
                if result is None:
                    want_gpu = False
                else:
                    want_gpu = True
                    cuda_tag, cuda_ver, cuda_url = result
                break
            else:
                print("  잘못된 입력입니다. 1 또는 2를 입력하세요.")

    elif default_gpu and cuda_tag is None:
        # CUDA 버전 감지 자체 실패 → 수동 선택
        result = _ask_cuda_manual()
        if result is None:
            want_gpu = False
        else:
            want_gpu = True
            cuda_tag, cuda_ver, cuda_url = result

    else:
        # 정상 감지 또는 GPU 없음 → 2지 선택
        print()
        print("  설치할 버전을 선택하세요:")
        if default_gpu:
            print(f"    1. GPU 버전  ({cuda_tag}, CUDA {cuda_ver})  [권장]")
            print("    2. CPU 버전")
        else:
            print("    1. CPU 버전  [권장]")
            if cuda_tag:
                print(f"    2. GPU 버전  ({cuda_tag}, CUDA {cuda_ver})")
            else:
                print("    2. GPU 버전  (드라이버 미지원 - 비권장)")
        while True:
            ans = input("  선택 (1 또는 2): ").strip()
            if ans == "1":
                want_gpu = default_gpu
                break
            elif ans == "2":
                want_gpu = not default_gpu
                break
            else:
                print("  잘못된 입력입니다. 1 또는 2를 입력하세요.")

    want_type = "cuda" if want_gpu else "cpu"

    # 이미 올바른 버전이면 스킵
    if (want_gpu and cuda_ok_now) or (not want_gpu and cpu_ok_now):
        ver, _ = _torch_info()
        print(f"  PyTorch {ver} ({want_type}) 이미 설치됨. 건너뜁니다.")
        return 0

    # 기존 버전 제거
    if installed:
        _uninstall()

    # 설치
    if want_gpu:
        ok = _install(cuda_url, f"GPU ({cuda_tag}, CUDA {cuda_ver})")
    else:
        ok = _install(_CPU_INDEX, "CPU")

    if not ok:
        print("[ERROR] PyTorch 설치 실패.")
        return 1

    # 설치 결과 출력
    print()
    _print_installed_info()

    # GPU 요청했는데 CPU 빌드가 설치된 경우 → 고정 버전으로 재시도
    if want_gpu and _installed_type() == "cpu":
        print()
        print(f"  [경고] CPU 빌드가 설치됨 — {cuda_tag} 인덱스에 최신 PyTorch CUDA 빌드 없음.")
        print("  이전 버전 CUDA 빌드로 재설치 시도합니다...")
        _uninstall()
        if _install_pinned_cuda(cuda_tag, cuda_url):
            print()
            _print_installed_info()
            if _installed_type() == "cpu":
                print("  [오류] CUDA 빌드 설치 실패. CPU 버전으로 사용하거나 나중에 다시 시도하세요.")
                return 1
        else:
            print("  [오류] CUDA 빌드 설치 실패. CPU 버전으로 사용하거나 나중에 다시 시도하세요.")
            return 1

    # CUDA 빌드는 됐는데 GPU 인식 실패
    if want_gpu and not _cuda_ok():
        print()
        print("  [경고] CUDA PyTorch 설치됐으나 GPU 인식 실패.")
        if driver_cuda:
            print(f"  드라이버 지원 CUDA: {driver_cuda:.1f}")
        print("  해결 방법:")
        print("    1. NVIDIA 드라이버 최신 버전으로 업데이트 후 재부팅")
        print("       -> https://www.nvidia.com/drivers")
        print("    2. 재부팅 후 install.bat 다시 실행")
        print("    3. GPU 안 되면 install.bat 에서 CPU 버전 선택")

    return 0


if __name__ == "__main__":
    sys.exit(main())
