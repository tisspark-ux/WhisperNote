"""styles.py — Gradio UI 전체 CSS."""

CSS = """
/* ── 전체 배경 ── */
body, .gradio-container {
    background: #0f1117 !important;
    font-family: 'Inter', 'Pretendard', -apple-system, sans-serif !important;
}

/* ── 헤더 ── */
#wn-header {
    padding: 2.4rem 0 1.6rem;
    text-align: center;
    border-bottom: 1px solid #1e2130;
    margin-bottom: 1.6rem;
}
#wn-header h1 {
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #e8eaf6;
    margin: 0 0 0.4rem;
}
#wn-header p {
    color: #6b7280;
    font-size: 0.92rem;
    margin: 0;
}

/* ── 카드 ── */
.wn-card {
    background: #161b27 !important;
    border: 1px solid #1e2130 !important;
    border-radius: 12px !important;
    padding: 1.2rem 1.4rem !important;
}

/* ── 섹션 레이블 ── */
.wn-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #4b5563;
    margin-bottom: 0.6rem;
}

/* ── 상태 뱃지 ── */
#record-status textarea {
    background: #0d1117 !important;
    border: 1px solid #1e2130 !important;
    border-radius: 8px !important;
    color: #9ca3af !important;
    font-size: 0.85rem !important;
}

/* ── 버튼 – 녹음 시작 ── */
#btn-start {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    border-radius: 10px !important;
    color: #fff !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    height: 48px !important;
    transition: opacity .2s !important;
}
#btn-start:hover { opacity: .85 !important; }

/* ── 버튼 – 녹음 종료 ── */
#btn-stop {
    background: linear-gradient(135deg, #ef4444, #f97316) !important;
    border: none !important;
    border-radius: 10px !important;
    color: #fff !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    height: 48px !important;
    transition: opacity .2s !important;
}
#btn-stop:hover { opacity: .85 !important; }
#btn-stop:disabled { opacity: .35 !important; }

/* ── 버튼 – 파이프라인 ── */
#btn-pipeline {
    background: linear-gradient(135deg, #0ea5e9, #6366f1) !important;
    border: none !important;
    border-radius: 10px !important;
    color: #fff !important;
    font-weight: 600 !important;
    height: 48px !important;
    width: 100% !important;
    font-size: 1rem !important;
    margin-top: 0.4rem !important;
    transition: opacity .2s !important;
}
#btn-pipeline:hover { opacity: .85 !important; }

/* ── 버튼 – 보조 ── */
.wn-btn-secondary {
    background: #1e2130 !important;
    border: 1px solid #2d3348 !important;
    border-radius: 8px !important;
    color: #9ca3af !important;
    font-size: 0.85rem !important;
    height: 38px !important;
    transition: background .2s !important;
}
.wn-btn-secondary:hover { background: #252b40 !important; color: #e5e7eb !important; }
.wn-btn-del:hover { border-color: #ef4444 !important; color: #ef4444 !important; }

/* ── 텍스트 박스 (결과) ── */
.wn-result textarea {
    background: #0d1117 !important;
    border: 1px solid #1e2130 !important;
    border-radius: 10px !important;
    color: #d1d5db !important;
    font-size: 0.88rem !important;
    line-height: 1.7 !important;
    padding: 1rem !important;
}

/* ── 드롭다운 ── */
.wn-dropdown select, .wn-dropdown input {
    background: #0d1117 !important;
    border: 1px solid #1e2130 !important;
    border-radius: 8px !important;
    color: #d1d5db !important;
}

/* ── 파일 경로 ── */
.wn-filepath textarea {
    background: transparent !important;
    border: none !important;
    border-top: 1px solid #1e2130 !important;
    border-radius: 0 !important;
    color: #4b5563 !important;
    font-size: 0.78rem !important;
    font-family: 'JetBrains Mono', monospace !important;
    padding: 0.5rem 0 0 !important;
}

/* ── 구분선 ── */
.wn-divider {
    border: none;
    border-top: 1px solid #1e2130;
    margin: 1rem 0;
}

/* ── 탭 ── */
.tab-nav button {
    background: transparent !important;
    border: none !important;
    color: #6b7280 !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    padding: 0.6rem 1.2rem !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
}
.tab-nav button.selected {
    color: #818cf8 !important;
    border-bottom-color: #818cf8 !important;
}

/* ── 파이프라인 상태 ── */
#pipeline-status textarea {
    background: #0a0f1a !important;
    border: 1px solid #1e2130 !important;
    border-radius: 8px !important;
    color: #6ee7b7 !important;
    font-size: 0.85rem !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Upload 박스 ── */
.wn-upload {
    border: 1.5px dashed #2d3348 !important;
    border-radius: 10px !important;
    background: #0d1117 !important;
}
.wn-upload:hover { border-color: #6366f1 !important; }

/* ── 오디오 레벨 미터 ── */
.wn-level-bar {
    background: #0d1117 !important;
    border: 1px solid #2d3348 !important;
    border-radius: 6px !important;
    padding: 6px 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
    color: #6ee7b7 !important;
    letter-spacing: 2px;
}
.wn-level-idle { color: #4b5563 !important; letter-spacing: normal; }
/* 레벨 미터 컨테이너 높이 고정 — 0.2s 갱신 시 레이아웃 흔들림 방지 */
#wn-level-wrap { min-height: 36px !important; height: 36px !important; overflow: hidden !important; }
#wn-level-wrap > div { height: 36px !important; }

/* ── 분류 설정 패널 ── */
.wn-cat-panel { margin-bottom: 1rem !important; position: relative !important; }
#btn-cat-close { position: absolute !important; top: 0.6rem !important; right: 0.6rem !important; width: auto !important; min-width: 70px !important; }
.wn-cat-col { border-right: 1px solid #1e2130; padding-right: 0.6rem !important; min-height: 160px; }
.wn-cat-col:last-child { border-right: none !important; }
.wn-cat-col-header {
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: #818cf8;
    padding: 0.3rem 0; border-bottom: 1px solid #2d3348; margin-bottom: 0.4rem;
}
/* Radio 스타일 */
.wn-cat-radio fieldset { border: none !important; padding: 0 !important; margin: 0 !important; }
.wn-cat-radio input[type="radio"] { display: none !important; }
.wn-cat-radio label {
    display: flex !important; align-items: center !important;
    padding: 0.25rem 0.4rem !important; border-radius: 5px !important;
    color: #9ca3af !important; font-size: 0.86rem !important;
    cursor: pointer !important; transition: background .12s !important;
    gap: 0.4rem !important;
}
.wn-cat-radio label:hover { background: #1e2130 !important; }
.wn-cat-radio label:has(input:checked) { background: #1e2130 !important; color: #e8eaf6 !important; font-weight: 500 !important; }
.wn-cat-radio label:has(input:checked)::before { content: "▶"; color: #818cf8; font-size: 0.6rem; }
.wn-cat-radio label:not(:has(input:checked))::before { content: "  "; }
/* 분류 소형 버튼 */
.wn-cat-btn-sm {
    background: #161b27 !important; border: 1px solid #2d3348 !important;
    border-radius: 5px !important; color: #6b7280 !important;
    font-size: 0.78rem !important; height: 28px !important;
    padding: 0 0.5rem !important; min-width: 0 !important;
    transition: all .12s !important;
}
.wn-cat-btn-sm:hover { border-color: #818cf8 !important; color: #818cf8 !important; background: #1e2130 !important; }
.wn-cat-btn-del:hover { border-color: #ef4444 !important; color: #ef4444 !important; }
/* 경로 표시 */
.wn-cat-path { font-size: 0.76rem !important; font-family: 'JetBrains Mono', monospace !important; color: #4b5563 !important; padding: 0.25rem 0 !important; }
.wn-cat-path-active { color: #818cf8 !important; }
/* 설정 버튼 */
#btn-cat-settings { background: #161b27 !important; border: 1px solid #2d3348 !important; border-radius: 8px !important; color: #6b7280 !important; height: 36px !important; min-width: 36px !important; }
#btn-cat-settings:hover { border-color: #818cf8 !important; color: #818cf8 !important; }

/* ── 전사 결과 헤더 행: 라벨 좌측, 라디오 우측 ── */
.wn-view-row { display: flex !important; align-items: center !important; justify-content: space-between !important; }
.wn-view-row > * { flex: 0 0 auto !important; }
.wn-view-radio { width: auto !important; }
.wn-view-radio fieldset { display: flex !important; flex-direction: row !important; gap: 0.5rem !important; border: none !important; padding: 0 !important; margin: 0 !important; }

/* ── 슬라이더 숫자 입력칸 너비 축소 ── */
.gradio-slider input[type="number"] {
    width: 48px !important;
    min-width: 0 !important;
    padding: 0 4px !important;
}

/* ── 파일 목록 ── */
#wn-file-list {
    max-height: 220px;
    overflow-y: auto;
    background: #0d1117;
    border: 1px solid #1e2130;
    border-radius: 8px;
    padding: 4px 0;
}
.wn-file-item {
    display: flex;
    align-items: center;
    padding: 5px 10px;
    cursor: pointer;
    border-radius: 4px;
    margin: 1px 4px;
    transition: background .1s;
    color: #9ca3af;
    font-size: 0.84rem;
    font-family: 'JetBrains Mono', monospace;
    user-select: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.wn-file-item:hover { background: #1e2130; color: #e5e7eb; }
.wn-file-item.selected { background: #1e2d4a; color: #818cf8; }
.wn-file-empty {
    padding: 16px;
    text-align: center;
    color: #4b5563;
    font-size: 0.82rem;
}
.wn-hidden-input {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
"""
