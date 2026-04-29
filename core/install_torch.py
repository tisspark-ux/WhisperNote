"""PyTorch GPU/CPU 선택 설치 스크립트."""
import os
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
_CUDA_INDEX = "https://download.pytorch.org/whl/cu124"
_CPU_INDEX  = "https://download.pytorch.org/whl/cpu"


def _detect_gpus():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return [g.strip() for g in r.stdout.strip().splitlines() if g.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return []


def _installed_type():
    """Returns 'cuda', 'cpu', or None."""
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


def _torch_ver():
    r = subprocess.run(
        [sys.executable, "-c", "import torch; print(torch.__version__)"],
        capture_output=True, text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else "?"


def _uninstall():
    print("  기존 PyTorch 제거 중...")
    subprocess.run(
        _PIP + ["uninstall", "-y"] + _TORCH_PKGS,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _install(cuda: bool) -> bool:
    if cuda:
        print("  PyTorch CUDA 12.4 버전 설치 중 (수 분 소요)...")
        idx = _CUDA_INDEX
    else:
        print("  PyTorch CPU 버전 설치 중...")
        idx = _CPU_INDEX
    r = subprocess.run(_PIP + ["install"] + _TORCH_PKGS + ["--index-url", idx] + _COMMON)
    return r.returncode == 0


def main() -> int:
    gpus = _detect_gpus()
    installed = _installed_type()

    print()
    if gpus:
        print("  [GPU 감지됨]")
        for g in gpus:
            print(f"    - {g}")
        default_gpu = True
    else:
        print("  [NVIDIA GPU 없음 - CPU 버전 권장]")
        default_gpu = False

    if installed:
        if installed == "cuda":
            ok_str = "CUDA 정상" if _cuda_ok() else "CUDA 인식 불가"
        else:
            ok_str = "정상"
        print(f"  [현재 설치] PyTorch {_torch_ver()} ({installed}, {ok_str})")
        cuda_ok_now = (installed == "cuda" and _cuda_ok())
        cpu_ok_now  = (installed == "cpu")
    else:
        print("  [현재 설치] PyTorch 없음")
        cuda_ok_now = cpu_ok_now = False

    print()
    if default_gpu:
        print("  설치할 버전을 선택하세요:")
        print("    1. GPU(CUDA 12.4) 버전  [권장]")
        print("    2. CPU 버전")
    else:
        print("  설치할 버전을 선택하세요:")
        print("    1. CPU 버전  [권장]")
        print("    2. GPU(CUDA 12.4) 버전")

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
        print(f"  PyTorch {_torch_ver()} ({want_type}) 이미 설치됨. 건너뜁니다.")
        return 0

    # 기존 버전 제거
    if installed:
        _uninstall()

    # 설치
    if not _install(want_gpu):
        print("[ERROR] PyTorch 설치 실패.")
        return 1

    print(f"  PyTorch ({want_type}) 설치 완료.")

    # 설치 후 CUDA 동작 확인
    if want_gpu:
        print("  CUDA 동작 확인 중...")
        if _cuda_ok():
            print(f"  CUDA 정상 동작 확인 완료. ({_torch_ver()})")
        else:
            print()
            print("  [경고] CUDA PyTorch 설치됐으나 GPU 인식 실패.")
            print("  원인 후보:")
            print("    1. NVIDIA 드라이버가 CUDA 12.4 를 지원하지 않음")
            print("       -> https://www.nvidia.com/drivers 에서 최신 드라이버 설치")
            print("    2. 드라이버 설치 후 재부팅 필요")
            print("    3. install.bat 을 다시 실행해 CPU 버전으로 전환 가능")
    return 0


if __name__ == "__main__":
    sys.exit(main())
