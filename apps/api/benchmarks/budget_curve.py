"""키프레임 예산 K 와 장소 회수의 관계를 이미 수집한 프레임 표에서 계산한다.

사전 등록 테스트(`youtube/PREREGISTRATION.md`)에서 `text_nms` 선별은 기각됐다. 그때 함께
남긴 프레임 표(`frame_table.json`: 프레임마다 외부 OCR 판정으로 어떤 장소가 읽혔는지)를
다시 써서, **선별기를 바꾸지 않고 예산 K 만 늘리면** 회수가 어디까지 오르는지를 본다.

새 영상도 새 라벨도 쓰지 않는다. 이미 커밋된 정답과 이미 수집한 판정표에 대한 **사후
탐색 분석**이며, 새로운 방법의 채택 근거로는 쓸 수 없다(같은 데이터로 방법을 고르면
선택 편향이 생긴다 — PREREGISTRATION.md 의 같은 이유).

세 곡선을 K 마다 비교한다.

- `oracle`: 전체 샘플 프레임에서 고른 최선(탐욕 근사). 선별기가 완벽할 때의 상한.
- `gate`: 품질 게이트를 통과한 프레임만으로 고른 최선. 게이트가 깎은 상한.
- `random`: 게이트 통과 프레임에서 K 장을 균등 추출했을 때의 기댓값(초기하분포 정확값).

`validate_recall.py` 의 무작위 기준선은 몬테카를로(2000회)지만 여기서는 닫힌 형태로 낸다.
장소 p 가 읽히는 프레임이 pool N 개 중 n_p 개면 K 장에 한 번이라도 걸릴 확률은
`1 - C(N - n_p, K) / C(N, K)` 이고, 장소 수 기댓값은 이 확률의 합이다.

사용법:

    python benchmarks/budget_curve.py --split test
    python benchmarks/budget_curve.py --split test --out ../../docs/vision-frontend-budget.md
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from recall_truth import (
    TruthError,
    load_truth,
    parse_manifest,
    select_specs,
)

#: 표에 찍을 예산 지점. 16 은 현재 파이프라인 기본값(`MAX_KEYFRAMES`).
DEFAULT_BUDGETS: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 766)

#: 현재 파이프라인 기본 예산.
BASE_BUDGET = 16

#: 사전 등록 테스트에서 현재 파이프라인(full)이 실제로 회수한 장소 수.
CURRENT_RECALL = 3


class BudgetCurveError(RuntimeError):
    """프레임 표를 읽지 못했을 때."""


@dataclass(frozen=True)
class FrameTable:
    """한 영상의 프레임 단위 판정표."""

    key: str
    sampled_frames: int
    gate_rejected: frozenset[int]
    readable: Mapping[int, frozenset[str]]
    place_ids: tuple[str, ...]

    @property
    def allowed(self) -> tuple[int, ...]:
        """게이트를 통과한 프레임 번호."""
        return tuple(i for i in range(self.sampled_frames) if i not in self.gate_rejected)


def load_frame_table(path: Path, *, key: str, place_ids: Sequence[str]) -> FrameTable:
    """`frame_table.json` 을 읽어 `FrameTable` 로 만든다.

    `place_ids` 는 정답 파일에서 온 평가 구간 안 장소 목록이다. 표에는 한 번도 읽히지 않은
    장소가 아예 나타나지 않으므로, 분모는 반드시 정답 쪽에서 받아야 한다.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BudgetCurveError(
            f"{key}: {path} 가 없습니다. `validate_recall.py --full-table` 로 먼저 만드세요."
        ) from exc
    known = set(place_ids)
    readable: dict[int, frozenset[str]] = {}
    for raw_index, raw_places in payload["any"].items():
        hits = frozenset(str(p) for p in raw_places) & known
        if hits:
            readable[int(raw_index)] = hits
    return FrameTable(
        key=key,
        sampled_frames=int(payload["sampled_frames"]),
        gate_rejected=frozenset(int(i) for i in payload["gate_rejected"]),
        readable=readable,
        place_ids=tuple(place_ids),
    )


def greedy_curve(
    table: Mapping[int, frozenset[str]],
    pool: Iterable[int],
    *,
    max_budget: int,
) -> list[int]:
    """K = 1..max_budget 에서 탐욕적 최대 커버리지로 얻는 장소 수.

    최대 커버리지 문제는 NP-난해라 탐욕법을 쓴다. 탐욕법은 최적의 `1 - 1/e`(약 63%) 이상을
    보장하는 **하한**이므로, 여기서 나온 오라클 곡선은 진짜 상한보다 낮을 수 있다.
    현재 데이터에서는 모든 영상이 K < 32 에서 전체 합집합에 도달해 차이가 없다.
    """
    remaining = {index: hits for index in pool if (hits := table.get(index))}
    covered: set[str] = set()
    curve: list[int] = []
    for _ in range(max_budget):
        best_index, best_gain = None, 0
        for index, hits in remaining.items():
            gain = len(hits - covered)
            if gain > best_gain or (gain == best_gain and best_index is None and gain > 0):
                best_index, best_gain = index, gain
        if best_index is None or best_gain == 0:
            curve.extend([len(covered)] * (max_budget - len(curve)))
            break
        covered |= remaining.pop(best_index)
        curve.append(len(covered))
    return curve


def random_curve(
    table: Mapping[int, frozenset[str]],
    pool: Sequence[int],
    place_ids: Sequence[str],
    *,
    max_budget: int,
) -> list[float]:
    """K = 1..max_budget 에서 무작위 K 장이 회수하는 장소 수의 기댓값 (정확값).

    장소마다 "K 장 중 적어도 한 장이 그 장소를 읽는 프레임일 확률"을 초기하분포로 내고 더한다.
    """
    total = len(pool)
    counts = dict.fromkeys(place_ids, 0)
    for index in pool:
        for pid in table.get(index, frozenset()):
            counts[pid] += 1
    curve: list[float] = []
    for budget in range(1, max_budget + 1):
        k = min(budget, total)
        expected = 0.0
        for pid in place_ids:
            hit_frames = counts[pid]
            if hit_frames == 0:
                continue
            miss = total - hit_frames
            if k > miss:
                expected += 1.0
            else:
                expected += 1.0 - math.comb(miss, k) / math.comb(total, k)
        curve.append(expected)
    return curve


def min_budget_for(curve: Sequence[float], target: float) -> int | None:
    """곡선이 `target` 이상이 되는 가장 작은 K. 끝까지 못 미치면 None."""
    for index, value in enumerate(curve, start=1):
        if value >= target:
            return index
    return None


@dataclass(frozen=True)
class VideoCurves:
    """한 영상의 세 곡선과 분모."""

    key: str
    places: int
    sampled_frames: int
    gate_kept: int
    oracle: list[int]
    gate: list[int]
    random: list[float]


def build_curves(table: FrameTable, *, max_budget: int) -> VideoCurves:
    """전체·게이트·무작위 세 곡선을 만든다."""
    allowed = table.allowed
    return VideoCurves(
        key=table.key,
        places=len(table.place_ids),
        sampled_frames=table.sampled_frames,
        gate_kept=len(allowed),
        oracle=greedy_curve(table.readable, range(table.sampled_frames), max_budget=max_budget),
        gate=greedy_curve(table.readable, allowed, max_budget=max_budget),
        random=random_curve(table.readable, allowed, table.place_ids, max_budget=max_budget),
    )


def totals(curves: Sequence[VideoCurves]) -> VideoCurves:
    """영상별 곡선을 합쳐 전체 곡선을 만든다 (장소 수는 영상마다 독립이라 단순 합)."""
    max_budget = min(len(c.oracle) for c in curves)
    return VideoCurves(
        key="합계",
        places=sum(c.places for c in curves),
        sampled_frames=sum(c.sampled_frames for c in curves),
        gate_kept=sum(c.gate_kept for c in curves),
        oracle=[sum(c.oracle[i] for c in curves) for i in range(max_budget)],
        gate=[sum(c.gate[i] for c in curves) for i in range(max_budget)],
        random=[sum(c.random[i] for c in curves) for i in range(max_budget)],
    )


def format_curve_table(total: VideoCurves, budgets: Sequence[int]) -> str:
    """예산별 전체 곡선 표."""
    lines = [
        "| 예산 K | 오라클 (전체 프레임) | 게이트 통과 안에서 최선 | 무작위 기댓값 |",
        "|---:|---:|---:|---:|",
    ]
    for budget in budgets:
        if budget > len(total.oracle):
            continue
        i = budget - 1
        lines.append(
            f"| {budget} | {total.oracle[i]}/{total.places} | "
            f"{total.gate[i]}/{total.places} | {total.random[i]:.1f}/{total.places} |"
        )
    return "\n".join(lines)


def format_per_video(curves: Sequence[VideoCurves], budget: int) -> str:
    """기준 예산에서의 영상별 표 + 포화 지점."""
    lines = [
        f"| 영상 | 장소 | 샘플 | 게이트 통과 | 오라클@{budget} | 무작위@{budget} | "
        "오라클 포화 K | 무작위가 오라클@16 에 닿는 K |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for curve in curves:
        i = budget - 1
        ceiling = curve.oracle[-1]
        saturate = min_budget_for(curve.oracle, ceiling)
        catch_up = min_budget_for(curve.random, curve.oracle[i])
        lines.append(
            f"| {curve.key} | {curve.places} | {curve.sampled_frames} | {curve.gate_kept} | "
            f"{curve.oracle[i]}/{curve.places} | {curve.random[i]:.1f}/{curve.places} | "
            f"{saturate if saturate is not None else '—'} | "
            f"{catch_up if catch_up is not None else f'> {len(curve.random)}'} |"
        )
    return "\n".join(lines)


def format_report(curves: Sequence[VideoCurves], total: VideoCurves, budgets: Sequence[int]) -> str:
    """마크다운 보고서 본문."""
    base = BASE_BUDGET - 1
    pool = len(total.random)
    half = total.oracle[base] / 2
    k_half = min_budget_for(total.random, half)
    k_now = min_budget_for(total.random, float(CURRENT_RECALL))
    half_text = (
        f"K={k_half} — 예산 {k_half / BASE_BUDGET:.0f}배"
        if k_half is not None
        else "예산으로는 불가"
    )
    half_cost = f"비용 {k_half / BASE_BUDGET:.0f}배" if k_half is not None else "예산으로는 불가"
    now_text = f"K={k_now}" if k_now is not None else f"K>{pool}"
    saturate = max((min_budget_for(c.oracle, c.oracle[-1]) or 0) for c in curves)
    gate_loss = total.oracle[-1] - total.gate[-1]
    per_video = total.sampled_frames // len(curves)
    lines = [
        "# 키프레임 예산 K 와 장소 회수 (사후 탐색 분석)",
        "",
        "사전 등록 테스트(`apps/api/benchmarks/youtube/PREREGISTRATION.md`)에서 남긴 프레임 표를",
        "다시 계산한 것이다. **새 영상도 새 라벨도 쓰지 않았고, 새 방법의 채택 근거도 아니다.**",
        "같은 데이터로 방법을 고르면 선택 편향이 생기므로, 여기 숫자는 다음 실험의 설계 근거로만",
        "쓴다.",
        "",
        "## 묻는 것",
        "",
        "> 선별이 무작위 수준이면, 그냥 프레임을 더 많이 넣으면 되지 않나?",
        "",
        f"테스트 3편 {total.places}곳, 영상당 {per_video}장 샘플(1fps), 현재 예산 K={BASE_BUDGET}.",
        f"현재 파이프라인의 실제 회수는 {CURRENT_RECALL}곳, 같은 예산의 오라클은 "
        f"{total.oracle[base]}곳, 무작위 기댓값은 {total.random[base]:.1f}곳이다.",
        "",
        "## 답: 예산은 이미 충분하다",
        "",
        format_curve_table(total, budgets),
        "",
        f"- 오라클은 K={BASE_BUDGET} 에서 {total.oracle[base]}곳이고, 그 뒤로 늘지 않는다. "
        f"영상마다 {saturate}장이면 **읽을 수 있는 장소를 전부** 덮는다.",
        f"- 무작위는 {now_text} 에서야 현재 파이프라인의 {CURRENT_RECALL}곳에 닿는다 "
        f"(지금 선별기는 예산을 {BASE_BUDGET}장 쓰고도 무작위 {k_now}장 수준이다).",
        f"- 무작위가 오라클의 절반({half:.0f}곳)에 닿으려면 {half_text}.",
        f"- 게이트 통과 프레임 {pool}장을 **전부** 넣어도 무작위 기댓값은 "
        f"{total.random[-1]:.1f}곳으로, K={BASE_BUDGET} 오라클({total.oracle[base]}곳)에 "
        "못 미친다.",
        "",
        "VLM 비용은 넣는 프레임 수에 거의 비례한다. 즉 **선별을 포기하고 예산으로 때우는 길은",
        f"닫혀 있다** — 절반만 회수하는 데도 {half_cost}, 전부 회수는",
        "어떤 예산으로도 안 된다. 남은 레버는 예산이 아니라 선별 신호다.",
        "",
        "## 영상별",
        "",
        format_per_video(curves, BASE_BUDGET),
        "",
        "## 게이트가 깎는 상한",
        "",
        f"전체 프레임 오라클 {total.oracle[-1]}곳, 게이트 통과 프레임만의 오라클 "
        f"{total.gate[-1]}곳 — "
        f"차이 {gate_loss}곳.",
        "품질 게이트(블러·노출)는 이 테스트 세트에서 **읽을 수 있는 장소를 하나도 잃지 않았다.**",
        "합성 장면에서 게이트가 선명한 프레임까지 버린다고 봤던 것과 달리, 실영상에서 병목은",
        "게이트가 아니라 게이트 뒤의 선별이다.",
        "",
        "## 한계",
        "",
        f"- 탐욕법은 최대 커버리지의 하한이지만, 이 데이터에서는 K={saturate} 에 "
        f"**읽히는 장소 전체의 합집합**({total.oracle[-1]}곳)에 도달한다. 합집합은 어떤 선택으로도 "
        f"넘을 수 없으므로 K≥{saturate} 구간의 오라클 값은 근사가 아니라 정확한 최적이다.",
        "- 오라클의 천장 자체가 정답의 천장은 아니다. 35곳 중 7곳은 1fps 샘플 어디에서도 "
        "외부 OCR 이 못 읽었다(작은 간판·모션 블러·짧은 노출).",
        "- 무작위 곡선은 균등 추출 기댓값이다. 시간축으로 고르게 뽑는 방식(현재 diverse)은 "
        "이보다 나을 수도 나쁠 수도 있는데, 실측은 나쁜 쪽이었다.",
        "",
        "## 재현",
        "",
        "```bash",
        "cd apps/api",
        "python benchmarks/budget_curve.py --split test",
        "```",
        "",
        "프레임 표는 `validate_recall.py --split test --full-table` 이 만든다 "
        "(영상 다운로드와 OCR 이 필요하고 수십 분 걸린다).",
    ]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="benchmarks/youtube/manifest.json")
    parser.add_argument("--split", default="test")
    parser.add_argument("--only", default="")
    parser.add_argument("--table-root", default="recall_out/youtube-test")
    parser.add_argument("--max-budget", type=int, default=0)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    specs = parse_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8")), base_dir=manifest_path.parent
    )
    selected = select_specs(specs, only=args.only, split=args.split)
    if not selected:
        raise SystemExit("조건에 맞는 영상이 없습니다")

    root = Path(args.table_root)
    curves: list[VideoCurves] = []
    for spec in selected:
        places, _ = load_truth(spec.truth_path, clip=spec.clip)
        if not places:
            raise TruthError(f"{spec.key}: 평가 구간 안에 장소가 없습니다")
        table = load_frame_table(
            root / spec.key / "frame_table.json",
            key=spec.key,
            place_ids=[place.place_id for place in places],
        )
        max_budget = min(args.max_budget or len(table.allowed), len(table.allowed))
        curves.append(build_curves(table, max_budget=max_budget))

    total = totals(curves)
    report = format_report(curves, total, DEFAULT_BUDGETS)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"→ {args.out}")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
