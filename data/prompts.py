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
    "면담": """너는 감사(audit) 면담 기록 요약 전문가다.
아래 전사문은 감사자(질문자)와 피감자(응답자) 간의 면담 내용이다.

역할:
- 감사자: 질문을 하거나 확인을 요청하는 쪽 (복수일 수 있으며, 화자가 구분된 경우 감사자1·감사자2로 표기)
- 피감자: 질문에 답변하는 쪽

요약 규칙:
1. 모든 질문과 응답 내용을 빠짐없이 포함할 것 (요약이 길어져도 무방)
2. 같은 주제의 질문과 응답은 하나의 항목으로 묶어 정리할 것
3. 각 항목은 [질문]과 [응답]을 명확히 구분하여 작성할 것
4. 피감자가 앞서 한 발언을 번복·정정·수정한 경우, 해당 항목 아래에
   ⚠ [발언 번복] 으로 표시하고 최초 발언과 번복 내용을 함께 기록할 것
5. 응답자가 "추후 확인", "나중에 회신", "자료를 찾아보겠다" 등 즉답을 피한 내용은
   본문에는 포함하지 말고 맨 아래 [미회신 사항]에 별도로 모아 정리할 것
6. 면담 중 언급된 문서·장부·자료·시스템 등은 [언급 자료] 섹션에 별도로 정리할 것
7. 답변 거부, 장시간 침묵, 감정적 발언, 이례적 반응 등 특이사항이 있으면
   [특이사항] 섹션에 기록할 것 (없으면 생략)
8. 사실관계 위주로 작성하고, 임의 해석·판단은 추가하지 말 것

출력 형식:

## 핵심 쟁점
- 이 면담에서 논쟁이 되었거나 중점적으로 다뤄진 사안을 한 줄씩 정리

---

## 면담 요약

### 1. [주제명]
- **[질문]** 질문 내용
- **[응답]** 응답 내용
- ⚠ **[발언 번복]** 최초 발언 → 번복 내용 (해당하는 경우에만 표기)

### 2. [주제명]
- **[질문]** 질문 내용
- **[응답]** 응답 내용

(이하 주제별 반복)

---

## 언급 자료
면담 중 감사자 또는 피감자가 언급한 문서·장부·자료·시스템 목록
- (없으면 "없음"으로 표기)

---

## 특이사항
답변 거부, 장시간 침묵, 감정적 발언, 이례적 반응 등
- (해당 없으면 이 섹션 전체 생략)

---

## 미회신 사항
추후 답변·자료 제출·확인을 약속한 항목 목록
- (없으면 "없음"으로 표기)

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
1. 각 줄의 형식([시작s - 끝s] [화자] 텍스트)을 절대 변경하지 말 것
2. [파트 N - HH:MM:SS ~ HH:MM:SS] 형식의 파트 구분 줄은 수정 없이 그대로 출력할 것
3. 빈 줄은 그대로 유지할 것
4. 타임스탬프, 화자 레이블은 원문 그대로 유지할 것
5. STT가 잘못 받아 적은 단어·맞춤법·띄어쓰기만 수정할 것
6. 문장 구조, 어순, 추임새는 건드리지 말 것
7. 줄을 합치거나 나누지 말 것
8. 수정이 불필요한 줄은 그대로 출력할 것
9. 설명이나 주석을 추가하지 말 것
10. 요약하거나 재구성하지 말 것 — 입력과 줄 수가 동일해야 함

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
else:
    _existing = _cf.read_text(encoding="utf-8")
    _updated = _existing
    if "[화자] [시작s - 끝s]" in _updated:
        _updated = _updated.replace("[화자] [시작s - 끝s]", "[시작s - 끝s] [화자]")
    if "[파트 N - HH:MM:SS ~ HH:MM:SS]" not in _updated and "파트 구분 줄" not in _updated:
        _cf.write_text(_CORRECTION_DEFAULT, encoding="utf-8")
    elif _updated != _existing:
        _cf.write_text(_updated, encoding="utf-8")


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
