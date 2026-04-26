from pathlib import Path

from config import BASE_DIR

PROMPTS_DIR = BASE_DIR / "prompts"
SUMMARY_DIR = PROMPTS_DIR / "summary"
CORRECTION_DIR = PROMPTS_DIR / "correction"

_SUMMARY_DEFAULTS: dict[str, str] = {
    "회의": """다음은 회의 전사문입니다. 아래 형식으로 요약해주세요.

## 핵심 내용
- 주요 논의 사항을 bullet point로 정리

## 결정 사항
- 회의에서 결정된 사항 정리 (없으면 "없음")

## 액션아이템
- 구체적인 액션아이템과 담당자 정리 (없으면 "없음")

---
전사문:
{transcript}
""",
    "면담": """다음은 면담 전사문입니다. 아래 형식으로 요약해주세요.

## 주요 내용
- 면담에서 논의된 핵심 내용을 bullet point로 정리

## 주요 발언
- 중요한 발언 내용 정리

## 후속 조치
- 면담 이후 필요한 조치나 확인 사항 (없으면 "없음")

---
전사문:
{transcript}
""",
    "보고서 리뷰": """다음은 보고서 리뷰 전사문입니다. 아래 형식으로 요약해주세요.

## 검토 의견
- 주요 검토 의견을 bullet point로 정리

## 수정 요청 사항
- 수정 또는 보완이 필요한 사항 (없으면 "없음")

## 승인/반려 여부
- 최종 결정 사항 정리

---
전사문:
{transcript}
""",
}

_CORRECTION_DEFAULT = """너는 STT 전사 오류 교정기다. 맞춤법·단어 수준의 오류만 수정한다.

규칙:
1. 각 줄의 형식([화자] [시작s - 끝s] 텍스트)을 절대 변경하지 말 것
2. 타임스탬프, 화자 레이블은 원문 그대로 유지할 것
3. STT가 잘못 받아 적은 단어·맞춤법·띄어쓰기만 수정할 것
4. 문장 구조, 어순, 추임새는 건드리지 말 것
5. 줄을 합치거나 나누지 말 것
6. 수정이 불필요한 줄은 그대로 출력할 것
7. 설명이나 주석을 추가하지 말 것

---
전사문:
{transcript}
"""

SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
CORRECTION_DIR.mkdir(parents=True, exist_ok=True)

for _name, _content in _SUMMARY_DEFAULTS.items():
    _f = SUMMARY_DIR / f"{_name}.txt"
    if not _f.exists():
        _f.write_text(_content, encoding="utf-8")

_cf = CORRECTION_DIR / "교정.txt"
if not _cf.exists():
    _cf.write_text(_CORRECTION_DEFAULT, encoding="utf-8")


def get_summary_prompt(summary_type: str) -> str:
    """요약 프롬프트 파일 로드. 파일 없으면 기본값 반환."""
    path = SUMMARY_DIR / f"{summary_type}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return _SUMMARY_DEFAULTS.get(summary_type, next(iter(_SUMMARY_DEFAULTS.values())))


def get_correction_prompt() -> str:
    """교정 프롬프트 파일 로드. 파일 없으면 기본값 반환."""
    path = CORRECTION_DIR / "교정.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return _CORRECTION_DEFAULT


def list_summary_types() -> list[str]:
    """prompts/summary/ 폴더의 요약 유형 목록 반환 (이름순)."""
    types = sorted(p.stem for p in SUMMARY_DIR.glob("*.txt"))
    return types if types else list(_SUMMARY_DEFAULTS.keys())
