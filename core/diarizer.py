"""
화자 분리 모듈 — resemblyzer + SpectralClustering 기반
HuggingFace 접근 불필요, pip install 후 완전 오프라인 동작.
(resemblyzer 가중치 ~17MB 는 pip 패키지에 내장 — 별도 다운로드 불필요)
"""

from __future__ import annotations

import numpy as np
import torch


def _load_encoder():
    from resemblyzer import VoiceEncoder
    # device=None 으로 두면 resemblyzer 가 GPU/CPU 자동 감지
    return VoiceEncoder()


def _estimate_num_speakers(embeddings: np.ndarray, max_speakers: int = 8) -> int:
    """화자 수 자동 추정.

    1단계: 평균 코사인 유사도로 단일 화자 여부 사전 판정
    2단계: Normalized Laplacian eigenvalue gap heuristic
    3단계: heuristic 이 1명으로 판정했지만 유사도가 낮으면 최소 2명으로 보정
    """
    from sklearn.metrics.pairwise import cosine_similarity

    n = len(embeddings)
    if n <= 1:
        return 1

    sim_matrix = cosine_similarity(embeddings)

    if n == 2:
        # 두 임베딩이 매우 유사하면 1명, 아니면 2명
        return 1 if float(sim_matrix[0, 1]) > 0.90 else 2

    # 대각선 제외 평균 유사도
    mask = ~np.eye(n, dtype=bool)
    mean_sim = float(sim_matrix[mask].mean())

    # 유사도가 매우 높으면 단일 화자로 확정
    if mean_sim > 0.93:
        return 1

    # Normalized Laplacian eigenvalue gap heuristic
    sim_clipped = np.clip(sim_matrix, 0, 1)
    d = sim_clipped.sum(axis=1)
    d_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(d, 1e-10)))
    laplacian = np.eye(n) - d_inv_sqrt @ sim_clipped @ d_inv_sqrt

    k_limit = min(max_speakers + 1, n)
    eigenvalues = np.sort(np.linalg.eigvalsh(laplacian))[:k_limit]
    gaps = np.diff(eigenvalues)
    k_est = int(np.argmax(gaps) + 1)

    # heuristic 이 1명으로 판정했지만 평균 유사도가 낮으면 → 최소 2명
    if k_est == 1 and mean_sim < 0.88:
        return 2

    return k_est


def diarize(
    audio_path: str,
    segments: list[dict],
    num_speakers: int | None = None,
) -> list[dict]:
    """
    각 세그먼트에 'speaker' 필드를 추가해 반환한다.

    Parameters
    ----------
    audio_path : str
        원본 오디오 파일 경로
    segments : list[dict]
        WhisperX transcribe 결과의 segments 리스트
        (각 dict 에 'start', 'end', 'text' 키 포함)
    num_speakers : int | None
        None 이면 자동 감지, 숫자 지정 시 해당 화자 수로 고정

    Returns
    -------
    segments 와 동일한 리스트 (in-place 수정 후 반환).
    각 dict 에 'speaker' 키('SPEAKER_00' 형식) 가 추가됨.
    """
    from resemblyzer import preprocess_wav
    from sklearn.cluster import SpectralClustering
    from sklearn.preprocessing import normalize

    encoder = _load_encoder()
    wav = preprocess_wav(audio_path)          # float32, 16 kHz mono
    sr = 16_000
    min_samples = int(sr * 0.5)              # 0.5초 미만 세그먼트는 임베딩 건너뜀

    valid_indices: list[int] = []            # 임베딩 추출에 성공한 세그먼트 인덱스
    embeddings: list[np.ndarray] = []

    for i, seg in enumerate(segments):
        start_s = int(seg.get("start", 0) * sr)
        end_s   = int(seg.get("end",   0) * sr)
        chunk   = wav[start_s:end_s]

        if len(chunk) < min_samples:
            continue

        emb = encoder.embed_utterance(chunk)
        embeddings.append(emb)
        valid_indices.append(i)

    if not embeddings:
        # 임베딩 가능한 세그먼트가 없으면 모두 SPEAKER_00 으로 처리
        for seg in segments:
            seg["speaker"] = "SPEAKER_00"
        return segments

    emb_matrix = normalize(np.array(embeddings))

    # 화자 수 결정
    n = len(emb_matrix)
    if num_speakers is None:
        k = _estimate_num_speakers(emb_matrix)
    else:
        k = max(1, min(num_speakers, n))

    # 클러스터링
    if k == 1 or n == 1:
        labels = [0] * n
    else:
        clustering = SpectralClustering(
            n_clusters=k,
            affinity="cosine",
            random_state=42,
            n_init=10,
        )
        labels = clustering.fit_predict(emb_matrix).tolist()

    # 유효 세그먼트에 화자 레이블 부여
    label_map: dict[int, str] = {
        idx: f"SPEAKER_{labels[pos]:02d}"
        for pos, idx in enumerate(valid_indices)
    }

    # 짧아서 건너뛴 세그먼트는 가장 가까운 앞 화자 레이블 사용
    last_speaker = "SPEAKER_00"
    for i, seg in enumerate(segments):
        if i in label_map:
            last_speaker = label_map[i]
        seg["speaker"] = last_speaker

    return segments
