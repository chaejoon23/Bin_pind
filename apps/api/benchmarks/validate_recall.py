"""장소 보존률(recall) 검증 — "얼마나 줄였나"가 아니라 "무엇을 잃었나"를 잰다.

## 왜 감소율로는 부족한가

`bench_keyframes.py`는 프레임을 몇 %로 줄였는지 보여준다. 그 숫자는 혼자서는 의미가
없다. 프레임을 1장만 남기면 감소율은 99%가 되고 장소는 거의 다 사라진다. 이 파이프라인이
지켜야 하는 것은 **줄이면서도 장소를 잃지 않는 것**이므로, 재야 하는 값은 감소율이 아니라
보존률이다.

## 판정자를 파이프라인 밖에 둔다

"이 프레임에서 간판을 읽을 수 있는가"를 파이프라인 자신의 `textness` 점수로 판정하면
동어반복이 된다(선별 점수에 이미 textness가 들어간다). 그래서 판정은 **외부 OCR
(tesseract)**이 한다. 파이프라인이 고른 프레임을 OCR에 넣어 정답 간판 문자열이 읽히는지
보고, 읽히면 그 장소는 살아남은 것으로 센다.

OCR은 같은 이미지에서도 `--psm` 모드에 따라 결과가 갈린다. 그래서 여러 모드의 출력을
합집합으로 쓰고, 문자열 비교는 정확 일치가 아니라 유사도 임계(기본 0.80)로 한다
(`CAFE LUMIERE`를 `care Lumiere`로 읽는 경우를 사람은 맞다고 보기 때문이다).
같은 기준을 보정 전/후에 **동일하게** 적용하므로 비교는 공정하다.

## 지표

- **장소 보존률** — 정답 장소 중 선별 프레임에서 간판이 읽힌 비율. 저조도/정상 노출로
  나눠서 본다. 저조도 쪽이 미니 ISP가 실제로 기여하는지를 보여준다.
- **오라클 보존률** — 선별 없이 모든 샘플 프레임을 OCR했을 때의 보존률. 상한선이다.
  이 값과의 차이가 "선별 때문에 잃은 것"이다.
- **장소당 프레임 수** — 1에 가까울수록 중복이 잘 접혔다. 재방문 장소가 여러 장
  남으면 같은 장소에 VLM 호출을 두 번 하는 셈이다.

## 사용

    # 정답을 아는 합성 장면으로
    python benchmarks/make_recall_scene.py --out-dir scene_out
    python benchmarks/validate_recall.py --scene-dir scene_out

    # 직접 찍은 영상으로 (ground_truth.json 을 손으로 작성)
    python benchmarks/validate_recall.py --video trip.mp4 --ground-truth truth.json

`ground_truth.json` 형식:

    {"places": [{"place_id": "p1", "sign_text": "CAFE LUMIERE",
                 "dark": false, "segments": [[0.0, 5.0], [55.0, 60.0]]}]}
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import cv2
from numpy import ndarray

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.vision import (  # noqa: E402
    KeyframeSelection,
    VisionFrontendConfig,
    build_embedder,
    select_keyframes,
)
from app.pipeline.vision.decode import read_bgr  # noqa: E402

# 여러 psm 모드의 출력을 합집합으로 쓴다. 한 모드만 쓰면 사람이 읽을 수 있는 간판도
# 모드에 따라 통째로 놓친다(psm 3은 큰 글자에, psm 6은 블록 텍스트에 강하다).
OCR_PSM_MODES: tuple[str, ...] = ("3", "6", "11")

# 문자열 유사도 임계. OCR 오인식(CAFE→care)을 사람 기준으로 흡수한다.
MATCH_THRESHOLD = 0.80

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")


@dataclass(frozen=True)
class PlaceTruth:
    """정답 장소 하나."""

    place_id: str
    sign_text: str
    dark: bool
    segments: tuple[tuple[float, float], ...]

    def contains(self, timestamp_sec: float) -> bool:
        return any(start <= timestamp_sec <= end for start, end in self.segments)


@dataclass
class RunResult:
    """설정 하나로 돌린 결과."""

    label: str
    selected_frames: int
    decoded_frames: int
    recovered: set[str]
    frames_per_place: dict[str, int]
    loss_reason: dict[str, str]
    elapsed_sec: float


def load_truth(path: Path) -> list[PlaceTruth]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    places: list[PlaceTruth] = []
    for entry in payload["places"]:
        places.append(
            PlaceTruth(
                place_id=str(entry["place_id"]),
                sign_text=str(entry["sign_text"]),
                dark=bool(entry.get("dark", False)),
                segments=tuple((float(a), float(b)) for a, b in entry["segments"]),
            )
        )
    if not places:
        raise SystemExit("ground_truth.json 에 places 가 비어 있습니다")
    return places


def _normalize(text: str) -> str:
    return _NON_ALNUM.sub("", text.upper())


def ocr_text(image: ndarray) -> str:
    """여러 psm 모드의 OCR 출력을 이어붙여 돌려준다."""
    if shutil.which("tesseract") is None:
        raise SystemExit(
            "tesseract 가 필요합니다.\n"
            "  macOS: brew install tesseract\n"
            "  Ubuntu: sudo apt install tesseract-ocr"
        )
    with tempfile.TemporaryDirectory() as work:
        image_path = Path(work) / "frame.png"
        cv2.imwrite(str(image_path), image)
        chunks: list[str] = []
        for psm in OCR_PSM_MODES:
            completed = subprocess.run(  # noqa: S603 - 고정 인자, 셸 없음
                ["tesseract", str(image_path), "stdout", "--psm", psm],
                capture_output=True,
                text=True,
                check=False,
            )
            chunks.append(completed.stdout)
    return " ".join(chunks)


def sign_is_readable(ocr_output: str, sign_text: str, *, threshold: float) -> bool:
    """OCR 결과 안에 간판 문자열이 (오인식을 허용해) 들어 있는지.

    정확 일치를 요구하면 사람이 읽을 수 있는 결과도 탈락한다. 반대로 토큰 하나만
    맞아도 통과시키면 관대해진다. 그래서 간판 전체 문자열과 같은 길이의 창을 OCR
    문자열 위로 훑으며 최대 유사도를 본다.
    """
    needle = _normalize(sign_text)
    haystack = _normalize(ocr_output)
    if not needle or len(haystack) < len(needle):
        return False
    matcher = SequenceMatcher(autojunk=False)
    matcher.set_seq2(needle)
    best = 0.0
    for start in range(len(haystack) - len(needle) + 1):
        matcher.set_seq1(haystack[start : start + len(needle)])
        best = max(best, matcher.ratio())
        if best >= threshold:
            return True
    return best >= threshold


def _place_of(places: list[PlaceTruth], timestamp_sec: float) -> PlaceTruth | None:
    for place in places:
        if place.contains(timestamp_sec):
            return place
    return None


def evaluate(
    selection: KeyframeSelection,
    places: list[PlaceTruth],
    *,
    label: str,
    threshold: float,
) -> RunResult:
    """선별 결과를 정답과 맞춰 보존률과 **손실 원인**을 낸다.

    보존률만 내면 "왜 잃었는지"를 알 수 없어 고칠 수가 없다. 장소를 잃는 경로는
    세 가지뿐이고, 각각 고쳐야 할 곳이 다르다.

    - 게이트 탈락 — 화질 게이트가 그 장소의 프레임을 다 버렸다 (임계/구제 문제)
    - 선별 제외 — 게이트는 통과했는데 대표로 뽑히지 않았다 (샷 분할/점수/예산 문제)
    - 읽기 실패 — 뽑혔는데 OCR이 간판을 못 읽었다 (보정 문제)
    """
    recovered: set[str] = set()
    frames_per_place: dict[str, int] = {place.place_id: 0 for place in places}
    loss_reason: dict[str, str] = {}

    for keyframe in selection.keyframes:
        place = _place_of(places, keyframe.timestamp_sec)
        if place is None:
            continue
        frames_per_place[place.place_id] += 1
        if place.place_id in recovered:
            continue
        detected = ocr_text(read_bgr(keyframe.path))
        if sign_is_readable(detected, place.sign_text, threshold=threshold):
            recovered.add(place.place_id)

    rejected_at = {frame.timestamp_sec for frame in selection.rejected}
    sampled_at = {frame.timestamp_sec for frame in selection.frame_stats}

    for place in places:
        if place.place_id in recovered:
            continue
        sampled = {ts for ts in sampled_at if place.contains(ts)}
        survived = sampled - rejected_at
        if not sampled:
            loss_reason[place.place_id] = "샘플 없음"
        elif not survived:
            loss_reason[place.place_id] = "게이트 탈락"
        elif frames_per_place[place.place_id] == 0:
            loss_reason[place.place_id] = "선별 제외"
        else:
            loss_reason[place.place_id] = "읽기 실패"

    return RunResult(
        label=label,
        selected_frames=selection.summary.selected_frames,
        decoded_frames=selection.summary.decoded_frames,
        recovered=recovered,
        frames_per_place=frames_per_place,
        loss_reason=loss_reason,
        elapsed_sec=selection.summary.elapsed_sec,
    )


def oracle_recall(
    video_path: Path, places: list[PlaceTruth], *, sample_fps: float, threshold: float
) -> set[str]:
    """선별 없이 모든 샘플 프레임을 OCR한 상한선.

    파이프라인이 고른 프레임의 보존률은 이 값과 비교해야 의미가 있다. 오라클이 놓친
    장소는 애초에 영상에서 읽을 수 없는 장소이고, 파이프라인 탓이 아니다.
    """
    capture = cv2.VideoCapture(str(video_path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(int(round(fps / sample_fps)), 1)

    recovered: set[str] = set()
    for index in range(0, total, step):
        remaining = [place for place in places if place.place_id not in recovered]
        if not remaining:
            break
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            break
        place = _place_of(places, index / fps)
        if place is None or place.place_id in recovered:
            continue
        if sign_is_readable(ocr_text(frame), place.sign_text, threshold=threshold):
            recovered.add(place.place_id)
    capture.release()
    return recovered


ABLATIONS: dict[str, dict[str, object]] = {
    # 전체 파이프라인 — 기준선
    "full": {},
    # 미니 ISP를 끈다. 저조도 장소가 살아남는지가 여기서 갈린다.
    "no-enhance": {"enhance": False},
    # 저조도 구제를 끈다 = 화질 게이트가 어두운 프레임을 먼저 버리는 예전 순서 재현.
    "no-rescue": {"rescue_luma_below": 0.0, "rescue_clip_low_above": 1.0},
    # 중복 제거를 끈다. 프레임 수가 몇 배로 늘어나는지 = dedup이 버는 비용.
    "no-dedup": {
        "scene_similarity_threshold": 1.0,
        "duplicate_shot_threshold": 1.0,
        "max_keyframes": 200,
    },
}


def _format_table(results: list[RunResult], places: list[PlaceTruth], oracle: set[str]) -> str:
    dark_ids = {place.place_id for place in places if place.dark}
    bright_ids = {place.place_id for place in places if not place.dark}
    total = len(places)

    def ratio(recovered: set[str], subset: set[str]) -> str:
        if not subset:
            return "—"
        return f"{len(recovered & subset)}/{len(subset)}"

    lines = [
        "| 설정 | 선별 프레임 | 장소 보존 | 정상 노출 | 저조도 | 장소당 프레임 | 소요 |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| _오라클 (선별 없음)_ | {results[0].decoded_frames} | "
        f"{len(oracle)}/{total} | {ratio(oracle, bright_ids)} | {ratio(oracle, dark_ids)} | "
        f"— | — |",
    ]
    for result in results:
        counted = [n for n in result.frames_per_place.values() if n > 0]
        per_place = sum(counted) / len(counted) if counted else 0.0
        lines.append(
            f"| {result.label} | {result.selected_frames} | "
            f"{len(result.recovered)}/{total} | "
            f"{ratio(result.recovered, bright_ids)} | {ratio(result.recovered, dark_ids)} | "
            f"{per_place:.1f} | {result.elapsed_sec:.1f}s |"
        )
    return "\n".join(lines)


def _format_losses(results: list[RunResult], places: list[PlaceTruth]) -> str:
    by_id = {place.place_id: place for place in places}
    lines = ["| 설정 | 잃은 장소 | 원인 |", "|---|---|---|"]
    for result in results:
        lost = [pid for pid in by_id if pid not in result.recovered]
        if not lost:
            lines.append(f"| {result.label} | 없음 | — |")
            continue
        for order, pid in enumerate(lost):
            place = by_id[pid]
            label = result.label if order == 0 else ""
            dark = " (저조도)" if place.dark else ""
            lines.append(
                f"| {label} | {place.sign_text}{dark} | {result.loss_reason.get(pid, '—')} |"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="장소 보존률 검증")
    parser.add_argument("--scene-dir", type=Path, help="make_recall_scene.py 의 출력 폴더")
    parser.add_argument("--video", type=Path, help="직접 찍은 영상")
    parser.add_argument("--ground-truth", type=Path, help="정답 JSON")
    parser.add_argument("--out-dir", type=Path, default=Path("recall_out"))
    parser.add_argument("--embedder", default="auto", help="auto | perceptual | dinov3")
    parser.add_argument("--sample-fps", type=float, default=1.0)
    parser.add_argument("--max-keyframes", type=int, default=16)
    parser.add_argument("--match-threshold", type=float, default=MATCH_THRESHOLD)
    parser.add_argument(
        "--ablations",
        default="full,no-enhance,no-rescue,no-dedup",
        help=f"쉼표 구분. 가능: {','.join(ABLATIONS)}",
    )
    args = parser.parse_args()

    if args.scene_dir is not None:
        video_path = args.scene_dir / "scene.mp4"
        truth_path = args.scene_dir / "ground_truth.json"
    elif args.video is not None and args.ground_truth is not None:
        video_path, truth_path = args.video, args.ground_truth
    else:
        raise SystemExit("--scene-dir 또는 (--video 와 --ground-truth)를 지정하세요")

    if not video_path.exists():
        raise SystemExit(f"영상을 찾을 수 없습니다: {video_path}")

    places = load_truth(truth_path)
    labels = [label.strip() for label in args.ablations.split(",") if label.strip()]
    unknown = [label for label in labels if label not in ABLATIONS]
    if unknown:
        raise SystemExit(f"알 수 없는 ablation: {unknown} (가능: {list(ABLATIONS)})")

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    embedder = build_embedder(args.embedder)

    print(
        f"영상 {video_path.name} · 장소 {len(places)}개 "
        f"(저조도 {sum(1 for p in places if p.dark)}개) · 임베더 {embedder.name}"
    )

    results: list[RunResult] = []
    for label in labels:
        fields: dict[str, object] = {
            "sample_fps": args.sample_fps,
            "max_keyframes": args.max_keyframes,
        }
        fields.update(ABLATIONS[label])
        config = VisionFrontendConfig(**fields)
        work_dir = out_dir / label
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True)

        print(f"\n[{label}] 실행 중...")
        selection = select_keyframes(video_path, work_dir, config=config, embedder=embedder)
        result = evaluate(selection, places, label=label, threshold=args.match_threshold)
        print(
            f"  선별 {result.selected_frames}장 / 디코딩 {result.decoded_frames}장 · "
            f"장소 {len(result.recovered)}/{len(places)}"
        )
        results.append(result)

    print("\n오라클(선별 없음) 계산 중...")
    oracle = oracle_recall(
        video_path, places, sample_fps=args.sample_fps, threshold=args.match_threshold
    )

    report = "\n\n".join(
        [
            "## 장소 보존률",
            _format_table(results, places, oracle),
            "### 잃은 장소",
            _format_losses(results, places),
            f"판정: 외부 OCR(tesseract, psm {'/'.join(OCR_PSM_MODES)} 합집합), "
            f"문자열 유사도 {args.match_threshold:.2f} 이상.",
        ]
    )
    report_path = out_dir / "recall_report.md"
    report_path.write_text(report + "\n", encoding="utf-8")
    print(f"\n{report}\n\n리포트: {report_path}")


if __name__ == "__main__":
    main()
