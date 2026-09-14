"""임베더 · 샷 분할 · 중복 제거 단위 테스트."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from app.pipeline.vision import embed as embed_module
from app.pipeline.vision.dedup import (
    adjacent_similarities,
    cosine_similarity_matrix,
    drop_near_duplicate_shots,
    segment_shots,
)
from app.pipeline.vision.embed import (
    PerceptualEmbedder,
    build_embedder,
    hsv_histogram,
    phash_bits,
)
from numpy.typing import NDArray

BgrImage = NDArray[np.uint8]


def _scene(seed: int, height: int = 180, width: int = 240) -> BgrImage:
    """seed마다 뚜렷하게 다른 합성 장면."""
    rng = np.random.default_rng(seed)
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :] = tuple(int(value) for value in rng.integers(20, 220, size=3))
    for _ in range(10):
        x1, y1 = int(rng.integers(0, width - 40)), int(rng.integers(0, height - 40))
        x2, y2 = x1 + int(rng.integers(20, 90)), y1 + int(rng.integers(20, 70))
        color = tuple(int(value) for value in rng.integers(0, 255, size=3))
        cv2.rectangle(image, (x1, y1), (x2, y2), color, -1)
    return image


def _jitter(image: BgrImage, shift: int = 2, seed: int = 0) -> BgrImage:
    """핸드헬드 흔들림 정도의 미세한 평행이동."""
    rng = np.random.default_rng(seed)
    matrix = np.array(
        [
            [1.0, 0.0, float(rng.integers(-shift, shift + 1))],
            [0.0, 1.0, float(rng.integers(-shift, shift + 1))],
        ],
        dtype=np.float32,
    )
    return cv2.warpAffine(
        image, matrix, (image.shape[1], image.shape[0]), borderMode=cv2.BORDER_REFLECT
    ).astype(np.uint8)


# --------------------------------------------------------------------------- 임베더


def test_phash_length_and_values() -> None:
    bits = phash_bits(_scene(1))
    assert bits.shape == (63,)  # 8x8 - DC
    assert set(np.unique(bits)).issubset({-1.0, 1.0})


def test_hsv_histogram_is_normalized() -> None:
    hist = hsv_histogram(_scene(1))
    assert hist.sum() == pytest.approx(1.0, abs=1e-5)


def test_embeddings_are_l2_normalized() -> None:
    embedder = PerceptualEmbedder()
    matrix = embedder.embed([_scene(1), _scene(2), _scene(3)])
    norms = np.linalg.norm(matrix, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_identical_frames_have_similarity_one() -> None:
    image = _scene(4)
    matrix = PerceptualEmbedder().embed([image, image.copy()])
    assert float(matrix[0] @ matrix[1]) == pytest.approx(1.0, abs=1e-5)


def test_different_scenes_are_less_similar_than_jittered_same_scene() -> None:
    base = _scene(5)
    embedder = PerceptualEmbedder()
    matrix = embedder.embed([base, _jitter(base, seed=1), _scene(6)])

    same_scene = float(matrix[0] @ matrix[1])
    other_scene = float(matrix[0] @ matrix[2])
    assert same_scene > other_scene


def test_build_embedder_perceptual() -> None:
    assert build_embedder("perceptual").name.startswith("perceptual")


def test_build_embedder_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="알 수 없는 임베더"):
        build_embedder("nope")


@pytest.mark.parametrize("error", [ImportError("no torch"), OSError("gated repo 403")])
def test_build_embedder_auto_falls_back_when_dinov3_unavailable(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def _raise(**_: object) -> None:
        raise error

    monkeypatch.setattr(embed_module, "Dinov3Embedder", _raise)
    assert build_embedder("auto").name.startswith("perceptual")


def test_build_embedder_dinov3_does_not_swallow_load_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(**_: object) -> None:
        raise OSError("gated repo 403")

    monkeypatch.setattr(embed_module, "Dinov3Embedder", _raise)
    with pytest.raises(OSError, match="gated"):
        build_embedder("dinov3")


# ----------------------------------------------------------------------- 유사도 유틸


def test_cosine_similarity_matrix_diagonal_is_one() -> None:
    matrix = PerceptualEmbedder().embed([_scene(1), _scene(2)])
    sims = cosine_similarity_matrix(matrix)
    assert np.allclose(np.diag(sims), 1.0, atol=1e-5)


def test_adjacent_similarities_length() -> None:
    matrix = PerceptualEmbedder().embed([_scene(i) for i in range(4)])
    assert adjacent_similarities(matrix).shape == (3,)


def test_adjacent_similarities_empty_for_single_frame() -> None:
    matrix = PerceptualEmbedder().embed([_scene(1)])
    assert adjacent_similarities(matrix).shape == (0,)


# ------------------------------------------------------------------------ 샷 분할


def test_identical_frames_form_one_shot() -> None:
    image = _scene(7)
    frames = [image.copy() for _ in range(6)]
    matrix = PerceptualEmbedder().embed(frames)

    shots = segment_shots(
        matrix,
        [float(index) for index in range(6)],
        list(range(6)),
        similarity_threshold=0.88,
        min_shot_gap_sec=1.0,
    )
    assert len(shots) == 1
    assert shots[0].frame_indices == list(range(6))


def test_scene_change_splits_shots() -> None:
    frames = [_scene(8)] * 4 + [_scene(9)] * 4
    matrix = PerceptualEmbedder().embed(frames)

    shots = segment_shots(
        matrix,
        [float(index) for index in range(8)],
        list(range(8)),
        similarity_threshold=0.90,
        min_shot_gap_sec=1.0,
    )
    assert len(shots) == 2
    assert shots[0].frame_indices == [0, 1, 2, 3]
    assert shots[1].frame_indices == [4, 5, 6, 7]


def test_min_shot_gap_prevents_oversegmentation() -> None:
    """장면이 매 프레임 바뀌어도 최소 샷 길이 안에서는 새 샷을 열지 않는다."""
    frames = [_scene(index) for index in range(6)]
    matrix = PerceptualEmbedder().embed(frames)

    shots = segment_shots(
        matrix,
        [float(index) for index in range(6)],
        list(range(6)),
        similarity_threshold=0.99,
        min_shot_gap_sec=10.0,  # 전체 길이보다 긴 최소 간격
    )
    assert len(shots) == 1


def test_segment_shots_empty_input() -> None:
    assert segment_shots(np.zeros((0, 4), dtype=np.float32), [], []) == []


def test_segment_shots_rejects_length_mismatch() -> None:
    matrix = PerceptualEmbedder().embed([_scene(1), _scene(2)])
    with pytest.raises(ValueError, match="길이가 일치"):
        segment_shots(matrix, [0.0], [0, 1])


def test_shot_timestamps_are_ordered() -> None:
    frames = [_scene(10)] * 3 + [_scene(11)] * 3
    matrix = PerceptualEmbedder().embed(frames)
    shots = segment_shots(
        matrix,
        [float(index) for index in range(6)],
        list(range(6)),
        similarity_threshold=0.90,
        min_shot_gap_sec=1.0,
    )
    for shot in shots:
        assert shot.start_sec <= shot.end_sec
    assert shots[0].end_sec <= shots[1].start_sec


# ------------------------------------------------------------------- 중복 샷 제거


def test_revisited_scene_is_dropped() -> None:
    """같은 장소로 돌아온 샷(A, B, A')에서 A'가 제거되어야 한다."""
    scene_a, scene_b = _scene(12), _scene(13)
    matrix = PerceptualEmbedder().embed([scene_a, scene_b, _jitter(scene_a, seed=2)])

    kept = drop_near_duplicate_shots(matrix, similarity_threshold=0.95)
    assert kept == [0, 1]


def test_distinct_shots_all_kept() -> None:
    matrix = PerceptualEmbedder().embed([_scene(index) for index in range(14, 18)])
    assert drop_near_duplicate_shots(matrix, similarity_threshold=0.95) == [0, 1, 2, 3]


def test_drop_duplicates_empty_input() -> None:
    assert drop_near_duplicate_shots(np.zeros((0, 4), dtype=np.float32)) == []


def test_drop_duplicates_keeps_first_occurrence() -> None:
    image = _scene(19)
    matrix = PerceptualEmbedder().embed([image, image.copy(), image.copy()])
    assert drop_near_duplicate_shots(matrix, similarity_threshold=0.95) == [0]
