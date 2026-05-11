"""data/vocab.py — 전문 용어 사전 파일 관리.

prompts/vocab/hotwords.txt   : 자주 쓰는 용어 (WhisperX + LLM 참고)
prompts/vocab/corrections.txt: STT 오인식 교정 규칙 (원문: 교정본)
"""
import re
from pathlib import Path

from config import BASE_DIR

VOCAB_DIR = BASE_DIR / "prompts" / "vocab"
HOTWORDS_FILE = VOCAB_DIR / "hotwords.txt"
CORRECTIONS_FILE = VOCAB_DIR / "corrections.txt"

_HOTWORDS_DEFAULT = """\
# 자주 쓰는 전문 용어 목록 (한 줄에 하나, # 으로 시작하는 줄은 주석)
# WhisperX 전사 힌트 및 Ollama 교정/요약 프롬프트에 자동으로 삽입됩니다.
# 예시:
# 현대모비스
# ADAS
# ECU
# OTA
"""

_CORRECTIONS_DEFAULT = """\
# STT 오인식 교정 규칙 (# 으로 시작하는 줄은 주석)
# 형식: 잘못전사된표현: 올바른표현
# 더 긴(구체적인) 패턴을 먼저 작성하세요.
# 영문은 대소문자를 구분하지 않습니다.
# 예시:
# 현 대 모비스: 현대모비스
# 모비수: 현대모비스
# mobis: 현대모비스
# 에이다스: ADAS
"""

# WhisperX initial_prompt 전체 권장 상한 (글자 수)
# Whisper context: 448 토큰, 한국어 1자 ≈ 1~2 토큰 → 안전 상한 약 220자
_PROMPT_MAX_CHARS = 220


def _init_files() -> None:
    VOCAB_DIR.mkdir(parents=True, exist_ok=True)
    if not HOTWORDS_FILE.exists():
        HOTWORDS_FILE.write_text(_HOTWORDS_DEFAULT, encoding="utf-8")
    if not CORRECTIONS_FILE.exists():
        CORRECTIONS_FILE.write_text(_CORRECTIONS_DEFAULT, encoding="utf-8")


_init_files()


# ---------------------------------------------------------------------------
# hotwords.txt
# ---------------------------------------------------------------------------

def load_hotwords() -> list[str]:
    """hotwords.txt 로드. 주석·빈 줄 제외."""
    if not HOTWORDS_FILE.exists():
        return []
    words = []
    for line in HOTWORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line)
    return words


def load_hotwords_as_csv() -> str:
    """hotwords.txt → UI 표시용 쉼표 구분 문자열."""
    return ", ".join(load_hotwords())


def save_hotwords_from_csv(csv_text: str) -> int:
    """UI의 쉼표 구분 문자열 → hotwords.txt 저장. 저장된 단어 수 반환."""
    words = [w.strip() for w in csv_text.split(",") if w.strip()]
    VOCAB_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 자주 쓰는 전문 용어 목록 (WhisperX 전사 힌트 및 Ollama 교정/요약 참고용)",
        "",
        *words,
    ]
    HOTWORDS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(words)


# ---------------------------------------------------------------------------
# corrections.txt
# ---------------------------------------------------------------------------

def load_corrections() -> list[tuple[str, str]]:
    """corrections.txt 로드. (원문, 교정본) 튜플 목록 반환.

    더 긴 패턴이 앞에 오도록 정렬해 구체적인 규칙이 먼저 적용된다.
    """
    if not CORRECTIONS_FILE.exists():
        return []
    rules: list[tuple[str, str]] = []
    for line in CORRECTIONS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            wrong, _, right = line.partition(":")
            wrong, right = wrong.strip(), right.strip()
            if wrong and right:
                rules.append((wrong, right))
    rules.sort(key=lambda r: len(r[0]), reverse=True)
    return rules


def apply_corrections(text: str) -> str:
    """corrections.txt 규칙을 텍스트에 적용한다.

    - 영문 포함 패턴: 대소문자 무시 + 단어 경계 (한글·영문·숫자에 인접하지 않을 때만 치환)
    - 순수 한국어 패턴: 단순 문자열 치환
    """
    rules = load_corrections()
    if not rules:
        return text
    for wrong, right in rules:
        if re.search(r"[a-zA-Z]", wrong):
            pattern = r"(?<![가-힣a-zA-Z\d])" + re.escape(wrong) + r"(?![가-힣a-zA-Z\d])"
            text = re.sub(pattern, right, text, flags=re.IGNORECASE)
        else:
            text = text.replace(wrong, right)
    return text


# ---------------------------------------------------------------------------
# WhisperX initial_prompt 빌더
# ---------------------------------------------------------------------------

def build_whisper_prompt(base_prompt: str) -> str:
    """base_prompt + hotwords → WhisperX initial_prompt 문자열.

    전체 길이가 _PROMPT_MAX_CHARS 를 넘지 않도록 단어 수를 자동 조절한다.
    hotwords 가 없으면 base_prompt 그대로 반환.
    """
    words = load_hotwords()
    if not words:
        return base_prompt

    # 단어를 하나씩 추가하며 길이 제한 체크
    added: list[str] = []
    for word in words:
        sep = ", " if added else ""
        candidate = base_prompt + " 관련 용어: " + ", ".join(added + [word]) + "."
        if len(candidate) > _PROMPT_MAX_CHARS:
            break
        added.append(word)

    if not added:
        return base_prompt
    return base_prompt + " 관련 용어: " + ", ".join(added) + "."


# ---------------------------------------------------------------------------
# LLM 프롬프트 컨텍스트 빌더
# ---------------------------------------------------------------------------

def build_llm_context() -> str:
    """교정/요약 LLM 프롬프트에 삽입할 vocab 컨텍스트 블록 생성.

    corrections 와 hotwords 모두 없으면 빈 문자열 반환.
    """
    words = load_hotwords()
    corrections = load_corrections()
    if not words and not corrections:
        return ""

    parts: list[str] = []
    if corrections:
        parts.append("[STT 오인식 교정 규칙]")
        parts.append("아래 오인식 패턴이 전사문에 남아 있으면 교정하세요:")
        for wrong, right in corrections:
            parts.append(f"  - {wrong} → {right}")
    if words:
        if parts:
            parts.append("")
        parts.append("[주요 전문 용어]")
        parts.append("아래 용어는 반드시 정확히 표기하세요:")
        parts.append("  " + ", ".join(words))

    return "\n".join(parts)
