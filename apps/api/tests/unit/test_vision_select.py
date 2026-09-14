"""문자 saliency와 키프레임 선별 엔드투엔드 테스트.

엔드투엔드 테스트는 ffmpeg으로 짧은 합성 영상을 즉석에서 만들어 돌린다. ffmpeg이 없는
환경에서는 skip 한다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest
from app.pipeline.vision import (
    PerceptualEmbedder,
    VisionFrontendConfig,
    select_keyframes,
    textness,
)
from app.pipeline.vision.types import RejectReason
from numpy.typing import NDArray

BgrImage = NDArray[np.uint8]

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe 가 필요합니다",
)


# ------------------------------------------------------------------------ textness


def _blank(height: int = 240, width: int = 360, value: int = 140) -> BgrImage:
    return np.full((height, width, 3), value, dtype=np.uint8)


def _with_sign(text: str = "BLUE BOTTLE COFFEE") -> BgrImage:
    image = _blank()
    cv2.rectangle(image, (20, 90), (340, 150), (245, 245, 240), -1)
    cv2.putText(image, text, (30, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2, cv2.LINE_AA)
    return image


def test_blank_frame_has_no_textness() -> None:
    assert textness(_blank()).score == pytest.approx(0.0)


def test_sign_frame_scores_higher_than_blank() -> None:
    assert textness(_with_sign()).score > textness(_blank()).score


def test_longer_sign_detects_more_regions() -> None:
    short = textness(_with_sign("CAFE"))
    long = textness(_with_sign("CAFE BLUE BOTTLE MANGWON SEOUL"))
    assert long.region_count > short.region_count


def test_textness_boxes_are_within_frame() -> None:
    image = _with_sign()
    result = textness(image)
    height, width = image.shape[:2]
    for box_x, box_y, box_w, box_h in result.boxes:
        assert 0 <= box_x and 0 <= box_y
        assert box_x + box_w <= width
        assert box_y + box_h <= height


def test_textness_score_is_bounded() -> None:
    result = textness(_with_sign("AAAA BBBB CCCC DDDD EEEE FFFF GGGG"))
    assert 0.0 <= result.score <= 1.0
    assert 0.0 <= result.area_ratio <= 1.0


# ----------------------------------------------------------------- 엔드투엔드 선별


def _write_video(path: Path, scenes: list[tuple[BgrImage, int]], fps: int = 10) -> None:
    """(프레임, 초) 목록을 mp4로 인코딩한다."""
    height, width = scenes[0][0].shape[:2]
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{width}x{height}",
            "-framerate",
            str(fps),
            "-i",
            "pipe:0",
            "-c:v",
            "libx264",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        stdin=subprocess.PIPE,
    )
    assert process.stdin is not None
    for frame, seconds in scenes:
        payload = frame.tobytes()
        for _ in range(seconds * fps):
            process.stdin.write(payload)
    process.stdin.close()
    assert process.wait() == 0


def _scene(seed: int, height: int = 240, width: int = 360) -> BgrImage:
    rng = np.random.default_rng(seed)
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :] = tuple(int(value) for value in rng.integers(60, 200, size=3))
    for _ in range(10):
        x1, y1 = int(rng.integers(0, width - 60)), int(rng.integers(0, height - 60))
        x2, y2 = x1 + int(rng.integers(30, 100)), y1 + int(rng.integers(30, 80))
        color = tuple(int(value) for value in rng.integers(0, 255, size=3))
        cv2.rectangle(image, (x1, y1), (x2, y2), color, -1)
    return image


@pytest.fixture
def three_scene_video(tmp_path: Path) -> Path:
    """서로 다른 3개 장면이 각 4초씩 이어지는 12초 영상."""
    path = tmp_path / "three_scenes.mp4"
    _write_video(path, [(_scene(1), 4), (_scene(2), 4), (_scene(3), 4)])
    return path


@requires_ffmpeg
def test_select_keyframes_collapses_static_scenes(three_scene_video: Path, tmp_path: Path) -> None:
    selection = select_keyframes(
        three_scene_video,
        tmp_path / "work",
        config=VisionFrontendConfig(
            sample_fps=1.0,
            max_keyframes=8,
            blur_reject_percentile=0.0,
            min_shot_gap_sec=1.0,
        ),
        embedder=PerceptualEmbedder(),
    )

    assert selection.summary.decoded_frames >= 10
    # 장면이 3개이므로 최종 프레임은 그 근방이어야 한다(정적 구간이 접혀야 함).
    assert 3 <= selection.summary.selected_frames <= 5
    assert selection.summary.reduction_ratio > 0.5


@requires_ffmpeg
def test_keyframe_files_exist_and_are_readable(three_scene_video: Path, tmp_path: Path) -> None:
    selection = select_keyframes(
        three_scene_video,
        tmp_path / "work",
        config=VisionFrontendConfig(sample_fps=1.0, blur_reject_percentile=0.0),
        embedder=PerceptualEmbedder(),
    )
    assert selection.keyframes
    for keyframe in selection.keyframes:
        assert keyframe.path.exists()
        assert cv2.imread(str(keyframe.path)) is not None


@requires_ffmpeg
def test_keyframes_are_time_ordered(three_scene_video: Path, tmp_path: Path) -> None:
    selection = select_keyframes(
        three_scene_video,
        tmp_path / "work",
        config=VisionFrontendConfig(sample_fps=1.0, blur_reject_percentile=0.0),
        embedder=PerceptualEmbedder(),
    )
    stamps = [keyframe.timestamp_sec for keyframe in selection.keyframes]
    assert stamps == sorted(stamps)


@requires_ffmpeg
def test_max_keyframes_is_respected(tmp_path: Path) -> None:
    path = tmp_path / "many.mp4"
    _write_video(path, [(_scene(seed), 2) for seed in range(8)])

    selection = select_keyframes(
        path,
        tmp_path / "work",
        config=VisionFrontendConfig(
            sample_fps=1.0, max_keyframes=3, min_shot_gap_sec=1.0, blur_reject_percentile=0.0
        ),
        embedder=PerceptualEmbedder(),
    )
    assert selection.summary.selected_frames <= 3
    assert any(item.reason is RejectReason.BUDGET for item in selection.rejected)


@requires_ffmpeg
def test_dark_scene_is_rescued_not_rejected(tmp_path: Path) -> None:
    """저조도 장면은 언더노출로 버려지지 않고 구제되어 살아남아야 한다.

    이 순서가 뒤집히면(게이트 먼저, 보정 나중) 실내에서 찍힌 장소가 전부 사라진다.
    """
    bright = _scene(21)
    dark = (_scene(22).astype(np.float32) * 0.12).astype(np.uint8)
    path = tmp_path / "dark.mp4"
    _write_video(path, [(bright, 4), (dark, 4)])

    selection = select_keyframes(
        path,
        tmp_path / "work",
        config=VisionFrontendConfig(
            sample_fps=1.0, blur_reject_percentile=0.0, min_shot_gap_sec=1.0
        ),
        embedder=PerceptualEmbedder(),
    )

    assert selection.summary.rescued_frames > 0
    assert not any(item.reason is RejectReason.UNDEREXPOSED for item in selection.rejected)

    # 어두운 구간(4초 이후)에서 최소 1장은 선별되어야 한다.
    late = [item for item in selection.keyframes if item.timestamp_sec >= 4.0]
    assert late, "저조도 구간에서 선별된 키프레임이 없습니다"
    assert any(item.rescued for item in selection.frame_stats)


@requires_ffmpeg
def test_summary_counts_are_consistent(three_scene_video: Path, tmp_path: Path) -> None:
    selection = select_keyframes(
        three_scene_video,
        tmp_path / "work",
        config=VisionFrontendConfig(sample_fps=1.0, blur_reject_percentile=0.0),
        embedder=PerceptualEmbedder(),
    )
    summary = selection.summary
    assert summary.decoded_frames == len(selection.frame_stats)
    assert summary.selected_frames == len(selection.keyframes)
    assert summary.shots_detected == len(selection.shots)
    assert summary.after_quality_gate <= summary.decoded_frames
    assert summary.selected_frames <= summary.after_quality_gate
    assert 0.0 <= summary.reduction_ratio <= 1.0


@requires_ffmpeg
def test_enhance_disabled_keeps_metrics_after_empty(
    three_scene_video: Path, tmp_path: Path
) -> None:
    selection = select_keyframes(
        three_scene_video,
        tmp_path / "work",
        config=VisionFrontendConfig(sample_fps=1.0, enhance=False, blur_reject_percentile=0.0),
        embedder=PerceptualEmbedder(),
    )
    # 보정을 끄면 구제되지 않은 프레임은 원본 그대로 나가고 metrics_after 가 비어 있다.
    # 구제된 프레임만 예외적으로 보정본이 나가므로 enhanced=True + metrics_after 존재.
    for keyframe in selection.keyframes:
        if keyframe.enhanced:
            assert keyframe.metrics_after is not None
        else:
            assert keyframe.metrics_after is None
