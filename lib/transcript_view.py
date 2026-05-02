"""transcript_view.py — 전사/교정 텍스트를 인터랙티브 HTML 테이블로 렌더링."""
import re
from html import escape

# 형식: [0.0s - 4.2s] [SPEAKER_00] 텍스트  (화자 선택적)
#       [0.0s - 4.2s] 텍스트
_SEG_RE = re.compile(
    r"^\[(\d+\.?\d*)s\s*-\s*(\d+\.?\d*)s\]\s*(?:\[([^\]]+)\]\s*)?(.+)$"
)


def parse_segments(text: str) -> list[dict]:
    segs = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _SEG_RE.match(line)
        if m:
            segs.append({
                "start":   float(m.group(1)),
                "end":     float(m.group(2)),
                "speaker": m.group(3) or "",
                "text":    m.group(4).strip(),
            })
        else:
            segs.append({"start": None, "end": None, "speaker": "", "text": line})
    return segs


def render_html(text: str) -> str:
    """전사/교정 텍스트를 클릭 가능한 HTML 테이블로 변환."""
    if not text or not text.strip():
        return ""

    segs = parse_segments(text)
    if not segs:
        return ""

    has_speaker = any(s["speaker"] for s in segs)
    has_time    = any(s["start"] is not None for s in segs)

    rows = []
    for seg in segs:
        timed = seg["start"] is not None
        data  = f' data-start="{seg["start"]}"' if timed else ""
        cls   = "wn-tr-row" if timed else "wn-tr-row wn-tr-row-plain"
        click = ' onclick="wnTrClick(event,this)"' if timed else ""

        time_td = speaker_td = ""
        if has_time:
            if timed:
                time_td = (
                    f'<td class="wn-tr-time">'
                    f'{seg["start"]:.1f}&#8202;–&#8202;{seg["end"]:.1f}s'
                    f'</td>'
                )
            else:
                time_td = '<td class="wn-tr-time"></td>'
        if has_speaker:
            speaker_td = f'<td class="wn-tr-speaker">{escape(seg["speaker"])}</td>'

        text_td = f'<td class="wn-tr-text">{escape(seg["text"])}</td>'
        rows.append(
            f'<tr class="{cls}"{data}{click}>'
            f'{time_td}{speaker_td}{text_td}'
            f'</tr>'
        )

    total   = len(segs)
    toolbar = (
        f'<div class="wn-tr-toolbar">'
        f'<span class="wn-tr-count">{total}개 세그먼트</span>'
        f'<button class="wn-tr-copy-btn" onclick="wnTrCopy(this)">&#128203; 선택 복사</button>'
        f'</div>'
    )

    return (
        f'<div class="wn-tr-wrap">'
        f'{toolbar}'
        f'<div class="wn-tr-scroll">'
        f'<table class="wn-tr-table"><tbody>{"".join(rows)}</tbody></table>'
        f'</div>'
        f'</div>'
    )
