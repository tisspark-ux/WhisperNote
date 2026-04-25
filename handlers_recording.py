"""handlers_recording.py — 녹음/폴링/마이크 테스트 이벤트 핸들러."""
from pathlib import Path

import gradio as gr

from instances import recorder, LOOPBACK_AUTO, REMOTE_AUTO, WASAPI_AUTO, MIX_AUTO
from worker import auto_worker
from handlers_category import _out_dir, _wav_dir


def handle_start_recording(device_idx, cat_data_val, l1_id, l2_id, l3_id,
                            chunk_minutes, model_name, summary_type_val):
    def _fail(msg):
        return (
            gr.update(interactive=True),
            gr.update(interactive=False),
            gr.update(interactive=False, value="⏸ 일시정지"),
            gr.update(interactive=True, value="마이크 테스트"),
            msg, "",
        )

    out_dir   = _wav_dir(cat_data_val, l1_id, l2_id, l3_id)
    chunk_min = int(chunk_minutes or 0)

    if device_idx == WASAPI_AUTO:
        file_path, msg = recorder.start(device_override=None, mixed=True,
                                         output_dir=out_dir, chunk_minutes=chunk_min)
    elif device_idx == MIX_AUTO:
        rdp_idx, _ = recorder.find_rdp_device()
        if rdp_idx is None:
            return _fail(
                "원격 마이크를 찾을 수 없습니다.\n"
                "RDP 클라이언트(원격 데스크톱 연결) → '옵션 더 보기' → '로컬 장치 및 리소스'\n"
                "→ '오디오 녹음' 항목을 활성화한 뒤 재연결하세요."
            )
        file_path, msg = recorder.start(device_override=rdp_idx, mixed=True,
                                         output_dir=out_dir, chunk_minutes=chunk_min)
    else:
        if device_idx == LOOPBACK_AUTO:
            loopback_idx, _ = recorder.find_loopback_device()
            if loopback_idx is None:
                return _fail(
                    "루프백 장치를 찾을 수 없습니다.\n"
                    "Windows 사운드 설정 → 녹음 탭 → 'Stereo Mix' 활성화 후 재시도하거나,\n"
                    "'(PC) 🎧 원격회의' 옵션을 사용해보세요."
                )
            device = loopback_idx
        elif device_idx == REMOTE_AUTO:
            rdp_idx, _ = recorder.find_rdp_device()
            if rdp_idx is None:
                return _fail(
                    "원격 마이크를 찾을 수 없습니다.\n"
                    "RDP 클라이언트(원격 데스크톱 연결) → '옵션 더 보기' → '로컬 장치 및 리소스'\n"
                    "→ '오디오 녹음' 항목을 활성화한 뒤 재연결하세요.\n"
                    "또는 설정 탭에서 [장치 목록 조회]로 [원격] 장치를 직접 선택하세요."
                )
            device = rdp_idx
        elif device_idx is None or device_idx == -1:
            device = None
        else:
            device = int(device_idx)
        file_path, msg = recorder.start(device_override=device, output_dir=out_dir,
                                         chunk_minutes=chunk_min)

    if file_path:
        p = Path(file_path)
        base = p.stem.split("_part")[0]
        transcript_out = _out_dir(cat_data_val, l1_id, l2_id, l3_id)
        auto_worker.reset(
            combined_path=transcript_out / f"{base}_transcript.txt",
            out_dir=transcript_out,
            model_name=model_name,
            summary_type=summary_type_val,
        )
        return (
            gr.update(interactive=False),
            gr.update(interactive=True),
            gr.update(interactive=True, value="⏸ 일시정지"),
            gr.update(interactive=False, value="마이크 테스트"),
            msg,
            file_path,
        )
    return (
        gr.update(interactive=True),
        gr.update(interactive=False),
        gr.update(interactive=False, value="⏸ 일시정지"),
        gr.update(interactive=True, value="마이크 테스트"),
        msg, "",
    )


def handle_stop_recording():
    file_path, msg = recorder.stop()
    return (
        gr.update(interactive=True),
        gr.update(interactive=False),
        gr.update(interactive=False, value="⏸ 일시정지"),
        gr.update(interactive=True, value="마이크 테스트"),
        msg,
        file_path or "",
    )


def handle_pause_resume():
    """일시정지 ↔ 재개 토글."""
    if recorder.paused:
        msg = recorder.resume()
        return gr.update(value="⏸ 일시정지"), msg
    else:
        msg = recorder.pause()
        return gr.update(value="▶ 재개"), msg


def handle_chunk_poll(current_view: str):
    """2초마다 청크/전사/요약 상태를 폴링해 UI 갱신."""
    r_status     = gr.update()
    r_file       = gr.update()
    r_transcript = gr.update()
    r_tfile      = gr.update()
    r_correction = gr.update()
    r_cfile      = gr.update()
    r_pipeline   = gr.update()
    r_display    = gr.update()
    r_view       = gr.update()
    r_dfile      = gr.update()
    r_summary    = gr.update()
    r_sfile      = gr.update()

    # 청크 알림
    msg = recorder.pop_chunk_message()
    if msg:
        r_status = gr.update(value=msg)
        if recorder.current_file:
            r_file = gr.update(value=str(recorder.current_file))

    # 전사 대기 작업 → worker 큐로 이동
    job = recorder.pop_pending_transcription()
    while job is not None:
        auto_worker.enqueue(job)
        job = recorder.pop_pending_transcription()

    # 녹음 종료 + recorder 큐 소진 + worker 아직 안 끝난 경우: 자동 교정 예약
    if (
        not recorder.recording
        and auto_worker._session_active
        and not auto_worker._finalize_triggered
        and not auto_worker.is_busy()
    ):
        auto_worker.enqueue_finalize()

    # 완료된 결과 반영
    result = auto_worker.pop_result()
    while result is not None:
        if "error" in result:
            r_pipeline = gr.update(value=f"⚠ {result['error']}")
        elif result.get("type") == "transcript":
            r_transcript = gr.update(value=result["transcript"])
            r_tfile      = gr.update(value=result["file_path"])
            r_pipeline   = gr.update(value=result["status"])
            if current_view == "원문":
                r_display = gr.update(value=result["transcript"])
                r_dfile   = gr.update(value=result["file_path"])
        elif result.get("type") == "correction":
            r_correction = gr.update(value=result["correction"])
            r_cfile      = gr.update(value=result["file_path"])
            r_pipeline   = gr.update(value=result["status"])
            r_display    = gr.update(value=result["correction"])
            r_view       = gr.update(value="교정")
            r_dfile      = gr.update(value=result["file_path"])
        elif result.get("type") == "summary":
            r_summary  = gr.update(value=result["summary"])
            r_sfile    = gr.update(value=result["file_path"])
            r_pipeline = gr.update(value=result["status"])
        result = auto_worker.pop_result()

    queue_text = auto_worker.get_status_text()
    r_queue = gr.update(value=queue_text)

    still_busy = recorder.recording or auto_worker.is_busy()
    r_timer = gr.update(active=still_busy)

    return (
        r_status, r_file,
        r_transcript, r_tfile,
        r_correction, r_cfile,
        r_pipeline, r_queue, r_timer,
        r_display, r_view, r_dfile,
        r_summary, r_sfile,
    )


def handle_mic_test(device_idx):
    """마이크 테스트 토글."""
    if recorder.testing:
        msg = recorder.stop_test()
        return gr.update(value="마이크 테스트"), msg

    if device_idx == WASAPI_AUTO:
        msg = recorder.start_test(mixed=True)
    elif device_idx == MIX_AUTO:
        rdp_idx, _ = recorder.find_rdp_device()
        if rdp_idx is None:
            return gr.update(value="마이크 테스트"), (
                "원격 마이크를 찾을 수 없습니다.\n"
                "RDP 클라이언트에서 '오디오 녹음' 리다이렉션을 활성화한 뒤 재연결하세요."
            )
        msg = recorder.start_test(device_override=rdp_idx, mixed=True)
    elif device_idx == LOOPBACK_AUTO:
        loopback_idx, _ = recorder.find_loopback_device()
        msg = recorder.start_test(device_override=loopback_idx)
    elif device_idx == REMOTE_AUTO:
        rdp_idx, _ = recorder.find_rdp_device()
        if rdp_idx is None:
            return gr.update(value="마이크 테스트"), (
                "원격 마이크를 찾을 수 없습니다.\n"
                "RDP 클라이언트에서 '오디오 녹음' 리다이렉션을 활성화한 뒤 재연결하세요."
            )
        msg = recorder.start_test(device_override=rdp_idx)
    elif device_idx is None or device_idx == -1:
        msg = recorder.start_test(device_override=None)
    else:
        msg = recorder.start_test(device_override=int(device_idx))

    if "실패" in msg:
        return gr.update(value="마이크 테스트"), msg
    return gr.update(value="테스트 중지"), msg
