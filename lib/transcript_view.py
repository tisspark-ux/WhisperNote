"""transcript_view.py — 전사/교정 텍스트를 인터랙티브 HTML 테이블로 렌더링."""
import re
from html import escape
from pathlib import Path


def audio_html(file_path: str) -> str:
    """오디오 파일 경로를 HTML <audio> 태그로 변환. Gradio /file= 엔드포인트 사용."""
    base = '<audio id="wn-audio-player" controls style="width:100%;outline:none;border-radius:6px"'
    if file_path:
        p = Path(file_path).as_posix()
        return f'{base} src="/file={p}"></audio>'
    return f'{base}></audio>'


def render_audio_map(audio_paths: dict) -> str:
    """파트 번호 → 오디오 파일 경로 매핑을 숨겨진 div data 속성으로 렌더링."""
    if not audio_paths:
        return '<div id="wn-audio-map" style="display:none"></div>'
    attrs = " ".join(
        f'data-part-{k}="/file={Path(str(v)).as_posix()}"'
        for k, v in sorted(audio_paths.items())
    )
    return f'<div id="wn-audio-map" style="display:none" {attrs}></div>'


def _fmt_ts(secs: float) -> str:
    """초를 HH:MM:SS.f 형식으로 변환. round() 로 부동소수점 오차 보정."""
    total = max(0.0, secs)
    tenths = int(round(total * 10)) % 10  # 0.1초 단위 반올림
    total_s = int(total)
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{tenths}"


def _hms_to_sec(hms: str) -> float:
    """HH:MM:SS 를 초로 변환."""
    h, mi, s = hms.split(":")
    return int(h) * 3600 + int(mi) * 60 + int(s)


# 신형: [0.0s - 4.2s] [SPEAKER_00] 텍스트  (화자 선택적)
_SEG_RE_NEW = re.compile(
    r"^\[(\d+\.?\d*)s\s*-\s*(\d+\.?\d*)s\]\s*(?:\[([^\]]+)\]\s*)?(.+)$"
)
# 구형: [SPEAKER_00] [0.0s - 4.2s] 텍스트
_SEG_RE_OLD = re.compile(
    r"^\[([^\]]+)\]\s*\[(\d+\.?\d*)s\s*-\s*(\d+\.?\d*)s\]\s*(.+)$"
)
# 파트 마커: [파트 N - HH:MM:SS ~ HH:MM:SS]
_PART_RE = re.compile(
    r"^\[파트\s+(\d+)\s*-\s*(\d{2}:\d{2}:\d{2})\s*~\s*(\d{2}:\d{2}:\d{2})\]$"
)


def _parse_lines(text: str) -> list[dict]:
    """전사 텍스트를 파싱해 세그먼트 + 파트 헤더 목록 반환.

    파트 헤더([파트 N - HH:MM:SS ~ HH:MM:SS])가 없어도
    타임스탬프가 크게 뒤로 리셋될 때(이전 end > 60s, 현재 start < 30s) 파트 경계로 자동 감지한다.
    교정 중 LLM이 파트 헤더를 제거한 파일도 올바르게 처리된다.
    """
    result = []
    current_part = 0
    current_part_offset = 0.0
    prev_end = -1.0  # 직전 세그먼트 end_sec (묵시적 경계 감지용)

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m_part = _PART_RE.match(line)
        if m_part:
            current_part = int(m_part.group(1))
            current_part_offset = _hms_to_sec(m_part.group(2))
            prev_end = -1.0
            result.append({"_part_header": True, "part_n": current_part, "label": line})
            continue
        m = _SEG_RE_NEW.match(line)
        if m:
            start = float(m.group(1))
            end   = float(m.group(2))
            if _is_implicit_part_boundary(current_part, prev_end, start):
                current_part += 1
                current_part_offset += prev_end
                prev_end = -1.0
                result.append({
                    "_part_header": True, "_implicit": True,
                    "part_n": current_part,
                    "label": f"[파트 {current_part}]",
                })
            result.append({
                "start": start, "end": end,
                "speaker":     m.group(3) or "",
                "text":        m.group(4).strip(),
                "part":        current_part,
                "part_offset": current_part_offset,
            })
            prev_end = end
            continue
        m = _SEG_RE_OLD.match(line)
        if m:
            start = float(m.group(2))
            end   = float(m.group(3))
            if _is_implicit_part_boundary(current_part, prev_end, start):
                current_part += 1
                current_part_offset += prev_end
                prev_end = -1.0
                result.append({
                    "_part_header": True, "_implicit": True,
                    "part_n": current_part,
                    "label": f"[파트 {current_part}]",
                })
            result.append({
                "start": start, "end": end,
                "speaker":     m.group(1).strip(),
                "text":        m.group(4).strip(),
                "part":        current_part,
                "part_offset": current_part_offset,
            })
            prev_end = end
            continue
        result.append({
            "start": None, "end": None, "speaker": "", "text": line,
            "part": current_part, "part_offset": current_part_offset,
        })
    return result


def _is_implicit_part_boundary(current_part: int, prev_end: float, cur_start: float) -> bool:
    """파트 헤더 없이 타임스탬프 리셋만으로 파트 경계 판단.

    조건: 현재 파트가 1 이상이고, 직전 end가 60초를 넘었는데
    새 세그먼트가 30초 미만으로 시작하면 새 파트로 판단한다.
    단일 파일(파트 없음)에는 current_part=0 이므로 절대 발동하지 않는다.
    """
    return (
        current_part > 0
        and prev_end > 60.0
        and cur_start < 30.0
        and (prev_end - cur_start) > 60.0
    )


def parse_segments(text: str) -> list[dict]:
    """하위 호환용 — 파트 헤더 제외하고 세그먼트만 반환."""
    return [s for s in _parse_lines(text) if not s.get("_part_header")]


def render_html(text: str) -> str:
    """전사/교정 텍스트를 클릭 가능한 HTML 테이블로 변환."""
    if not text or not text.strip():
        return ""

    items = _parse_lines(text)
    if not items:
        return ""

    segs = [s for s in items if not s.get("_part_header")]
    has_multi_part = any(s.get("_part_header") for s in items)
    has_speaker    = any(s["speaker"] for s in segs)
    has_time       = any(s["start"] is not None for s in segs)

    # 파트 헤더 colspan 계산
    col_count = 1  # 내용 열 항상 있음
    if has_time or has_multi_part:
        col_count += 1
    if has_speaker:
        col_count += 1

    # 헤더
    thead_cells = ""
    if has_time or has_multi_part:
        thead_cells += '<th class="wn-tr-th wn-tr-time">시간</th>'
    if has_speaker:
        thead_cells += '<th class="wn-tr-th wn-tr-speaker">발화자</th>'
    thead_cells += '<th class="wn-tr-th wn-tr-text">내용</th>'
    thead = f'<thead><tr class="wn-tr-head">{thead_cells}</tr></thead>'

    rows = []
    for item in items:
        if item.get("_part_header"):
            rows.append(
                f'<tr class="wn-tr-part-header">'
                f'<td colspan="{col_count}" class="wn-tr-part-label">{escape(item["label"])}</td>'
                f'</tr>'
            )
            continue

        timed  = item["start"] is not None
        data   = f' data-start="{item["start"]}"' if timed else ""
        part_n = item.get("part", 0)
        pd     = f' data-part="{part_n}"' if part_n else ""
        cls    = "wn-tr-row" if timed else "wn-tr-row wn-tr-row-plain"

        time_td = speaker_td = ""
        if has_time or has_multi_part:
            if timed:
                offset  = item.get("part_offset", 0.0)
                # 합본: 파트 오프셋 더해 누적 시간 표시 / 단일: 그대로
                disp_s = _fmt_ts(offset + item["start"]) if has_multi_part else _fmt_ts(item["start"])
                disp_e = _fmt_ts(offset + item["end"])   if has_multi_part else _fmt_ts(item["end"])
                time_td = (
                    f'<td class="wn-tr-time">'
                    f'{disp_s}&#8202;&#8211;&#8202;{disp_e}'
                    f'</td>'
                )
            else:
                time_td = '<td class="wn-tr-time"></td>'
        if has_speaker:
            speaker_td = f'<td class="wn-tr-speaker">{escape(item["speaker"])}</td>'

        text_td = f'<td class="wn-tr-text">{escape(item["text"])}</td>'
        rows.append(
            f'<tr class="{cls}"{data}{pd}>'
            f'{time_td}{speaker_td}{text_td}'
            f'</tr>'
        )

    total   = len(segs)
    toolbar = (
        f'<div class="wn-tr-toolbar">'
        f'<span class="wn-tr-count">{total}개 세그먼트</span>'
        f'<button class="wn-tr-copy-btn">&#128203; 선택 복사</button>'
        f'</div>'
    )

    return (
        f'<div class="wn-tr-wrap">'
        f'{toolbar}'
        f'<div class="wn-tr-scroll">'
        f'<table class="wn-tr-table">{thead}<tbody>{"".join(rows)}</tbody></table>'
        f'</div>'
        f'</div>'
    )
