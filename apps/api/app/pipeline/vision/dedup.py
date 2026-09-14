"""장면 분할과 중복 제거.

브이로그는 한 가게에서 수십 초를 머문다. 1 fps로 뽑으면 거의 동일한 프레임이 수십 장 나오고,
이걸 그대로 VLM에 넣으면 토큰만 쓰고 새 정보는 얻지 못한다. 여기서는 임베딩 코사인 유사도로
연속 프레임을 샷으로 묶고(온라인 1-pass), 샷마다 대표 1장만 남긴다.

샷 분할은 인접 프레임 유사도가 임계 아래로 떨어지는 지점을 컷으로 보는 고전적 방식이다
(Yeung & Liu, "Efficient Matching and Clustering of Video Shots", ICIP 1995의 인접 유사도
기반 분할을 단순화). 핸드헬드 흔들림 때문에 유사도가 한 프레임만 튀는 경우가 많아,
`min_shot_gap_sec`로 최소 샷 길이를 두어 과분할을 막는다.
"""

from __future__ import annotations

import numpy as np
import structlog
from numpy.typing import NDArray

from app.pipeline.vision.types import ShotSegment

logger = structlog.get_logger(__name__)

Embedding = NDArray[np.float32]


def cosine_similarity_matrix(embeddings: Embedding) -> NDArray[np.float32]:
    """L2 정규화된 임베딩들의 전체 코사인 유사도 행렬."""
    return (embeddings @ embeddings.T).astype(np.float32)


def adjacent_similarities(embeddings: Embedding) -> NDArray[np.float32]:
    """인접 프레임 간 코사인 유사도. 길이는 N-1."""
    if len(embeddings) < 2:
        return np.zeros(0, dtype=np.float32)
    sims: NDArray[np.float32] = np.sum(embeddings[:-1] * embeddings[1:], axis=1).astype(np.float32)
    return sims


def segment_shots(
    embeddings: Embedding,
    timestamps: list[float],
    frame_indices: list[int],
    *,
    similarity_threshold: float = 0.88,
    min_shot_gap_sec: float = 1.5,
) -> list[ShotSegment]:
    """연속 프레임을 샷으로 묶는다.

    Args:
        embeddings: (N, D) L2 정규화 임베딩.
        timestamps: 각 프레임의 영상 내 시각(초).
        frame_indices: 각 프레임의 원본 샘플 인덱스.
        similarity_threshold: 이 값 이상이면 같은 샷.
        min_shot_gap_sec: 새 샷을 열 수 있는 최소 경과 시간.

    Returns:
        시간순 `ShotSegment` 리스트.
    """
    count = len(frame_indices)
    if count == 0:
        return []
    if not (count == len(timestamps) == len(embeddings)):
        raise ValueError("embeddings, timestamps, frame_indices 길이가 일치해야 합니다")

    sims = adjacent_similarities(embeddings)
    shots: list[ShotSegment] = []
    current: list[int] = [0]
    shot_start_time = timestamps[0]

    for position in range(1, count):
        similar = bool(sims[position - 1] >= similarity_threshold)
        long_enough = (timestamps[position] - shot_start_time) >= min_shot_gap_sec
        if similar or not long_enough:
            current.append(position)
            continue

        shots.append(
            ShotSegment(
                shot_id=len(shots),
                start_sec=timestamps[current[0]],
                end_sec=timestamps[current[-1]],
                frame_indices=[frame_indices[pos] for pos in current],
            )
        )
        current = [position]
        shot_start_time = timestamps[position]

    shots.append(
        ShotSegment(
            shot_id=len(shots),
            start_sec=timestamps[current[0]],
            end_sec=timestamps[current[-1]],
            frame_indices=[frame_indices[pos] for pos in current],
        )
    )

    logger.info(
        "shots_segmented",
        frames=count,
        shots=len(shots),
        threshold=similarity_threshold,
        mean_adjacent_similarity=float(sims.mean()) if len(sims) else 1.0,
    )
    return shots


def drop_near_duplicate_shots(
    shot_embeddings: Embedding,
    *,
    similarity_threshold: float = 0.95,
) -> list[int]:
    """샷 대표 임베딩끼리 다시 비교해, 앞서 나온 샷과 거의 같은 샷을 버린다.

    브이로그는 같은 가게를 여러 번 돌아온다(먹는 컷 → 인테리어 → 다시 먹는 컷). 인접 비교만
    하면 이게 서로 다른 샷으로 남으므로, 전역 비교로 한 번 더 걸러낸다. 그리디 방식이라
    앞선 샷이 항상 살아남는다(시간 순서 보존).

    Args:
        shot_embeddings: (S, D) 샷 대표 임베딩.
        similarity_threshold: 이 값 이상이면 중복으로 판단.

    Returns:
        살아남은 샷의 인덱스(오름차순).
    """
    if len(shot_embeddings) == 0:
        return []

    kept: list[int] = [0]
    for index in range(1, len(shot_embeddings)):
        sims = shot_embeddings[kept] @ shot_embeddings[index]
        if float(sims.max()) < similarity_threshold:
            kept.append(index)

    logger.info(
        "duplicate_shots_dropped",
        shots_in=len(shot_embeddings),
        shots_out=len(kept),
        threshold=similarity_threshold,
    )
    return kept
