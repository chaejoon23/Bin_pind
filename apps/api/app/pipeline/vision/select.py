"""키프레임 선별 오케스트레이터.

`select_keyframes`가 이 패키지의 유일한 공개 진입점이다. 전체 흐름:

    디코딩(ffmpeg, 균일 샘플링)
      → 프레임별 화질 지표 + 간판 텍스트 점수 + 저조도 구제 + 임베딩  [청크 스트리밍]
      → 화질 게이트 (복원해도 못 읽는 프레임만 탈락)
      → 샷 분할 (인접 임베딩 유사도)
      → 샷별 대표 1장 (readability_score 최대)
      → 전역 중복 샷 제거 (같은 가게 재방문 컷 병합)
      → 예산 컷 (max_keyframes)
      → 미니 ISP 보정 후 JPEG 저장

저조도 구제가 화질 게이트보다 **앞에** 있는 것이 의도된 순서다. 게이트를 먼저 두면 실내에서
찍힌 어두운 프레임이 전부 언더노출로 탈락해, 영상에 분명히 나온 실내 장소가 결과에서 통째로
사라진다. 그래서 게이트의 역할은 "품질이 낮은 프레임 제거"가 아니라 "복원해도 읽을 수 없는
프레임 제거"다.

메모리 상한을 위해 프레임 픽셀은 청크(기본 32장)만 들고 있고, 최종 선별된 프레임만 다시 읽는다.
파이프라인 규칙대로 DB에 접근하지 않으며, 임시 디렉토리는 호출자가 준 `work_dir` 아래에만 만든다.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import NamedTuple

import numpy as np
import structlog
from numpy.typing import NDArray

from app.pipeline.vision import decode, dedup, isp, quality, textness
from app.pipeline.vision.embed import Embedder, PerceptualEmbedder
from app.pipeline.vision.types import (
    FrameStats,
    Keyframe,
    KeyframeSelection,
    QualityMetrics,
    RejectedFrame,
    RejectReason,
    SelectionSummary,
    ShotSegment,
    VisionFrontendConfig,
)

logger = structlog.get_logger(__name__)

_CHUNK_SIZE = 32
_DUPLICATE_SHOT_SIMILARITY = 0.95


class _FrameAnalysis(NamedTuple):
    """프레임 1장의 분석 결과(픽셀은 포함하지 않음)."""

    metrics: QualityMetrics
    rescued: bool
    metrics_rescued: QualityMetrics | None


def _needs_rescue(metrics: QualityMetrics, config: VisionFrontendConfig) -> bool:
    """저조도 구제 대상인지. 복원 불가 수준이면 구제하지 않는다(그냥 탈락)."""
    if (
        metrics.luma_mean < config.unrecoverable_luma_below
        or metrics.clipped_low_ratio > config.unrecoverable_clip_low_above
    ):
        return False
    return (
        metrics.luma_mean < config.rescue_luma_below
        or metrics.clipped_low_ratio >= config.rescue_clip_low_above
    )


def _analyze_chunk(
    paths: list[Path], embedder: Embedder, config: VisionFrontendConfig
) -> tuple[list[_FrameAnalysis], NDArray[np.float32]]:
    """프레임 청크를 읽어 지표와 임베딩을 계산하고 픽셀은 버린다.

    어두운 프레임은 여기서 먼저 구제 보정을 받는다. 그래야 지표·문자 점수·임베딩이 모두
    "VLM이 실제로 보게 될 프레임" 기준으로 계산된다.
    """
    analyses: list[_FrameAnalysis] = []
    embed_inputs: list[decode.BgrImage] = []

    for path in paths:
        image = decode.read_bgr(path)
        metrics = quality.compute_metrics(image, textness=textness.textness(image).score)
        if _needs_rescue(metrics, config):
            rescued_image, _ = isp.rescue_exposure(image)
            metrics_rescued = quality.compute_metrics(
                rescued_image, textness=textness.textness(rescued_image).score
            )
            analyses.append(_FrameAnalysis(metrics, True, metrics_rescued))
            embed_inputs.append(rescued_image)
        else:
            analyses.append(_FrameAnalysis(metrics, False, None))
            embed_inputs.append(image)

    return analyses, embedder.embed(embed_inputs)


def _quality_gate(
    stats: list[FrameStats], config: VisionFrontendConfig
) -> tuple[list[int], list[RejectedFrame]]:
    """화질 기준으로 프레임을 걸러낸다.

    Returns:
        (통과한 프레임의 리스트 내 위치, 탈락 기록)
    """
    lapvars = np.array(
        [item.effective_metrics.sharpness_lapvar for item in stats], dtype=np.float64
    )
    relative_cut = float(np.percentile(lapvars, config.blur_reject_percentile))
    luma_min, luma_max = config.luma_range

    kept: list[int] = []
    rejected: list[RejectedFrame] = []
    for position, item in enumerate(stats):
        metrics = item.effective_metrics
        if metrics.clipped_low_ratio > config.clipped_ratio_max or metrics.luma_mean < luma_min:
            rejected.append(
                RejectedFrame(
                    frame_index=item.index,
                    timestamp_sec=item.timestamp_sec,
                    reason=RejectReason.UNDEREXPOSED,
                    detail=f"luma={metrics.luma_mean:.3f} clip_low={metrics.clipped_low_ratio:.3f}",
                )
            )
            continue
        if metrics.clipped_high_ratio > config.clipped_ratio_max or metrics.luma_mean > luma_max:
            rejected.append(
                RejectedFrame(
                    frame_index=item.index,
                    timestamp_sec=item.timestamp_sec,
                    reason=RejectReason.OVEREXPOSED,
                    detail=(
                        f"luma={metrics.luma_mean:.3f} clip_high={metrics.clipped_high_ratio:.3f}"
                    ),
                )
            )
            continue
        too_blurry = (
            metrics.sharpness_lapvar < config.min_sharpness_lapvar
            or metrics.sharpness_lapvar < relative_cut
        )
        if too_blurry:
            rejected.append(
                RejectedFrame(
                    frame_index=item.index,
                    timestamp_sec=item.timestamp_sec,
                    reason=RejectReason.BLUR,
                    detail=f"lapvar={metrics.sharpness_lapvar:.2f} cut={relative_cut:.2f}",
                )
            )
            continue
        kept.append(position)

    return kept, rejected


def _pick_shot_representatives(
    shots: list[ShotSegment],
    index_to_position: dict[int, int],
    stats: list[FrameStats],
    *,
    sharpness_ref: float,
    text_weight: float,
) -> list[tuple[int, int, float]]:
    """샷마다 점수가 가장 높은 프레임 1장을 고른다.

    Returns:
        (shot_id, 프레임 리스트 내 위치, 점수) 리스트.
    """
    picks: list[tuple[int, int, float]] = []
    for shot in shots:
        best_position = -1
        best_score = -1.0
        for frame_index in shot.frame_indices:
            position = index_to_position[frame_index]
            score = quality.readability_score(
                stats[position].effective_metrics,
                sharpness_ref=sharpness_ref,
                text_weight=text_weight,
            )
            if score > best_score:
                best_score = score
                best_position = position
        picks.append((shot.shot_id, best_position, best_score))
    return picks


def select_keyframes(
    video_path: Path,
    work_dir: Path,
    *,
    config: VisionFrontendConfig | None = None,
    embedder: Embedder | None = None,
) -> KeyframeSelection:
    """영상에서 VLM에 올릴 키프레임을 고른다.

    Args:
        video_path: 원본 영상 파일.
        work_dir: 중간 프레임과 결과 JPEG를 쓸 디렉토리. 호출자가 생성/정리한다.
        config: 선별 설정. None이면 기본값.
        embedder: 프레임 임베더. None이면 `PerceptualEmbedder`(추가 의존성 없음).

    Returns:
        선별 결과와 집계. `keyframes[i].path`가 VLM에 넣을 JPEG 경로다.
    """
    cfg = config or VisionFrontendConfig()
    active_embedder = embedder or PerceptualEmbedder()
    started = time.perf_counter()

    frames_dir = work_dir / "frames"
    out_dir = work_dir / "keyframes"
    duration = decode.probe_duration_sec(video_path)
    sampled = decode.extract_frames(
        video_path,
        frames_dir,
        sample_fps=cfg.sample_fps,
        max_frames=cfg.max_decoded_frames,
        long_edge_px=cfg.long_edge_px,
    )

    # --- 1 pass: 저조도 구제 + 지표 + 임베딩 ---
    analyses: list[_FrameAnalysis] = []
    embedding_chunks: list[NDArray[np.float32]] = []
    for start in range(0, len(sampled), _CHUNK_SIZE):
        chunk = sampled[start : start + _CHUNK_SIZE]
        chunk_analyses, embeddings = _analyze_chunk(
            [path for _, path in chunk], active_embedder, cfg
        )
        analyses.extend(chunk_analyses)
        embedding_chunks.append(embeddings)
    all_embeddings = np.vstack(embedding_chunks).astype(np.float32)

    probe = decode.read_bgr(sampled[0][1])
    height, width = probe.shape[:2]
    stats = [
        FrameStats(
            index=index,
            timestamp_sec=timestamp,
            width=width,
            height=height,
            metrics=analyses[index].metrics,
            rescued=analyses[index].rescued,
            metrics_rescued=analyses[index].metrics_rescued,
        )
        for index, (timestamp, _) in enumerate(sampled)
    ]
    rescued_count = sum(1 for item in stats if item.rescued)
    if rescued_count:
        logger.info("frames_rescued", count=rescued_count, of=len(stats))

    lapvars = np.array(
        [item.effective_metrics.sharpness_lapvar for item in stats], dtype=np.float64
    )
    sharpness_ref = float(np.percentile(lapvars, 90))

    # --- 2 pass: 화질 게이트 ---
    kept_positions, rejected = _quality_gate(stats, cfg)
    if not kept_positions:
        logger.warning("all_frames_rejected", video=str(video_path))
        kept_positions = [int(np.argmax(lapvars))]
        rejected = [item for item in rejected if item.frame_index != stats[kept_positions[0]].index]

    # --- 3 pass: 샷 분할 ---
    shots = dedup.segment_shots(
        all_embeddings[kept_positions],
        [stats[position].timestamp_sec for position in kept_positions],
        [stats[position].index for position in kept_positions],
        similarity_threshold=cfg.scene_similarity_threshold,
        min_shot_gap_sec=cfg.min_shot_gap_sec,
    )
    index_to_position = {stats[position].index: position for position in kept_positions}

    picks = _pick_shot_representatives(
        shots,
        index_to_position,
        stats,
        sharpness_ref=sharpness_ref,
        text_weight=cfg.text_weight,
    )

    # --- 4 pass: 전역 중복 샷 제거 ---
    representative_embeddings = np.vstack(
        [all_embeddings[position] for _, position, _ in picks]
    ).astype(np.float32)
    surviving = dedup.drop_near_duplicate_shots(
        representative_embeddings, similarity_threshold=_DUPLICATE_SHOT_SIMILARITY
    )
    dropped_as_duplicate = set(range(len(picks))) - set(surviving)
    for order in sorted(dropped_as_duplicate):
        _, position, _ = picks[order]
        rejected.append(
            RejectedFrame(
                frame_index=stats[position].index,
                timestamp_sec=stats[position].timestamp_sec,
                reason=RejectReason.DUPLICATE,
                detail="앞선 샷과 유사도 >= 0.95",
            )
        )
    picks = [picks[order] for order in surviving]

    # --- 5 pass: 예산 컷 ---
    if len(picks) > cfg.max_keyframes:
        ranked = sorted(picks, key=lambda item: item[2], reverse=True)
        chosen = ranked[: cfg.max_keyframes]
        for _, position, _ in ranked[cfg.max_keyframes :]:
            rejected.append(
                RejectedFrame(
                    frame_index=stats[position].index,
                    timestamp_sec=stats[position].timestamp_sec,
                    reason=RejectReason.BUDGET,
                    detail=f"max_keyframes={cfg.max_keyframes}",
                )
            )
        picks = sorted(chosen, key=lambda item: stats[item[1]].timestamp_sec)

    # --- 6 pass: 보정 후 저장 ---
    path_by_index = {index: path for index, (_, path) in enumerate(sampled)}
    keyframes: list[Keyframe] = []
    for shot_id, position, score in picks:
        item = stats[position]
        image = decode.read_bgr(path_by_index[item.index])
        metrics_after: QualityMetrics | None = None
        if cfg.enhance:
            image, report = isp.enhance_for_vlm(
                image,
                noise_sigma=item.effective_metrics.noise_sigma,
                sharpness_lapvar=item.effective_metrics.sharpness_lapvar,
                sharpness_ref=sharpness_ref,
            )
            metrics_after = quality.compute_metrics(image, textness=textness.textness(image).score)
            logger.debug(
                "frame_enhanced",
                frame_index=item.index,
                stages=report.stages,
                gamma=round(report.gamma, 3),
            )
        elif item.rescued:
            # 보정을 끄더라도 구제된 프레임은 구제본을 내보내야 한다. 원본을 내보내면
            # 게이트 통과 근거(구제 후 지표)와 실제 VLM 입력이 달라진다.
            image, _ = isp.rescue_exposure(image)
            metrics_after = item.metrics_rescued
        out_path = out_dir / f"kf_{item.index:06d}_t{item.timestamp_sec:07.2f}.jpg"
        decode.write_jpeg(image, out_path, quality=cfg.jpeg_quality)
        keyframes.append(
            Keyframe(
                frame_index=item.index,
                shot_id=shot_id,
                timestamp_sec=item.timestamp_sec,
                path=out_path,
                selection_score=score,
                enhanced=cfg.enhance or item.rescued,
                metrics=item.metrics,
                metrics_after=metrics_after,
            )
        )

    decoded = len(sampled)
    selected = len(keyframes)
    summary = SelectionSummary(
        video_duration_sec=duration,
        decoded_frames=decoded,
        rescued_frames=rescued_count,
        after_quality_gate=len(kept_positions),
        shots_detected=len(shots),
        selected_frames=selected,
        reduction_ratio=1.0 - (selected / decoded) if decoded else 0.0,
        embedder=active_embedder.name,
        elapsed_sec=time.perf_counter() - started,
    )
    logger.info(
        "keyframes_selected",
        video=str(video_path),
        decoded=decoded,
        rescued=rescued_count,
        gate=summary.after_quality_gate,
        shots=summary.shots_detected,
        selected=selected,
        reduction=round(summary.reduction_ratio, 4),
        elapsed_sec=round(summary.elapsed_sec, 2),
    )
    return KeyframeSelection(
        keyframes=keyframes,
        shots=shots,
        rejected=rejected,
        frame_stats=stats,
        summary=summary,
        config=cfg,
    )
