"""예산 K–회수 곡선 계산 (benchmarks/budget_curve.py)."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks"))

from budget_curve import (  # noqa: E402
    BudgetCurveError,
    FrameTable,
    build_curves,
    greedy_curve,
    load_frame_table,
    min_budget_for,
    random_curve,
    totals,
)


def test_greedy_curve_picks_largest_cover_first() -> None:
    table = {0: frozenset({"a"}), 1: frozenset({"b", "c"}), 2: frozenset({"c"})}
    assert greedy_curve(table, range(3), max_budget=3) == [2, 3, 3]


def test_greedy_curve_pads_when_nothing_left_to_cover() -> None:
    table = {0: frozenset({"a"})}
    assert greedy_curve(table, range(5), max_budget=4) == [1, 1, 1, 1]


def test_greedy_curve_empty_table_is_all_zero() -> None:
    assert greedy_curve({}, range(5), max_budget=3) == [0, 0, 0]


def test_greedy_curve_respects_pool() -> None:
    """풀 밖 프레임은 아무리 좋아도 고르지 않는다 (게이트 탈락 프레임)."""
    table = {0: frozenset({"a", "b", "c"}), 1: frozenset({"d"})}
    assert greedy_curve(table, [1], max_budget=2) == [1, 1]


def test_random_curve_matches_hypergeometric_by_hand() -> None:
    """프레임 4장 중 1장만 장소를 담고 있으면 K 장에 걸릴 확률은 K/4."""
    table = {0: frozenset({"a"})}
    curve = random_curve(table, [0, 1, 2, 3], ["a"], max_budget=4)
    assert curve == pytest.approx([0.25, 0.5, 0.75, 1.0])


def test_random_curve_sums_places_independently() -> None:
    table = {0: frozenset({"a"}), 1: frozenset({"b"})}
    curve = random_curve(table, [0, 1, 2, 3], ["a", "b"], max_budget=2)
    # K=1: 각 0.25 → 0.5. K=2: 각 0.5 → 1.0.
    assert curve == pytest.approx([0.5, 1.0])


def test_random_curve_counts_unreadable_place_as_zero() -> None:
    """표에 한 번도 안 나오는 장소는 어떤 예산으로도 회수되지 않는다."""
    curve = random_curve({0: frozenset({"a"})}, [0, 1], ["a", "ghost"], max_budget=2)
    assert curve == pytest.approx([0.5, 1.0])


def test_random_curve_never_exceeds_greedy() -> None:
    """무작위 기댓값은 같은 K 의 최적 커버리지를 넘을 수 없다."""
    table = {i: frozenset({f"p{i % 5}"}) for i in range(20)}
    pool = list(range(20))
    places = [f"p{i}" for i in range(5)]
    rand = random_curve(table, pool, places, max_budget=20)
    greedy = greedy_curve(table, pool, max_budget=20)
    assert all(r <= g + 1e-9 for r, g in zip(rand, greedy, strict=True))


def test_random_curve_reaches_full_pool_exactly() -> None:
    """풀 전체를 뽑으면 기댓값은 읽히는 장소 수와 같다."""
    table = {0: frozenset({"a"}), 1: frozenset({"b"})}
    curve = random_curve(table, [0, 1], ["a", "b", "ghost"], max_budget=2)
    assert curve[-1] == pytest.approx(2.0)


def test_random_curve_monte_carlo_agreement() -> None:
    """몬테카를로(validate_recall 의 기준선 방식)와 같은 값인지 교차 확인."""
    import random as _random

    table = {0: frozenset({"a"}), 3: frozenset({"a", "b"}), 7: frozenset({"c"})}
    pool = list(range(10))
    places = ["a", "b", "c"]
    exact = random_curve(table, pool, places, max_budget=4)
    rng = _random.Random(0)
    draws = 20000
    for budget in (1, 2, 3, 4):
        hits = 0.0
        for _ in range(draws):
            found: set[str] = set()
            for index in rng.sample(pool, budget):
                found |= table.get(index, frozenset())
            hits += len(found)
        assert hits / draws == pytest.approx(exact[budget - 1], abs=0.03)


def test_min_budget_for_finds_first_index() -> None:
    assert min_budget_for([0.0, 1.5, 3.0], 1.5) == 2
    assert min_budget_for([0.0, 1.0], 9.0) is None


def _write_table(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "sampled_frames": 6,
                "gate_rejected": [4, 5],
                "any": {"0": ["a"], "1": ["b"], "4": ["c"]},
                "sign": {"0": ["a"]},
            }
        ),
        encoding="utf-8",
    )


def test_load_frame_table_drops_places_outside_truth(tmp_path: Path) -> None:
    """정답에 없는 장소(다른 구간 것)는 표에서 걸러낸다."""
    path = tmp_path / "frame_table.json"
    _write_table(path)
    table = load_frame_table(path, key="v", place_ids=["a", "b"])
    assert table.readable == {0: frozenset({"a"}), 1: frozenset({"b"})}
    assert table.allowed == (0, 1, 2, 3)


def test_load_frame_table_missing_file(tmp_path: Path) -> None:
    with pytest.raises(BudgetCurveError, match="full-table"):
        load_frame_table(tmp_path / "none.json", key="v", place_ids=["a"])


def test_build_curves_separates_gate_ceiling(tmp_path: Path) -> None:
    """게이트 탈락 프레임에서만 읽히는 장소는 게이트 곡선에서 빠진다."""
    path = tmp_path / "frame_table.json"
    _write_table(path)
    table = load_frame_table(path, key="v", place_ids=["a", "b", "c"])
    curves = build_curves(table, max_budget=4)
    assert curves.places == 3
    assert curves.gate_kept == 4
    assert curves.oracle[-1] == 3
    assert curves.gate[-1] == 2


def test_totals_sums_videos() -> None:
    def make(key: str, places: int) -> FrameTable:
        return FrameTable(
            key=key,
            sampled_frames=4,
            gate_rejected=frozenset(),
            readable={i: frozenset({f"{key}{i}"}) for i in range(places)},
            place_ids=tuple(f"{key}{i}" for i in range(places)),
        )

    curves = [build_curves(make("x", 2), max_budget=4), build_curves(make("y", 3), max_budget=4)]
    total = totals(curves)
    assert total.places == 5
    assert total.oracle[-1] == 5
    assert total.random[-1] == pytest.approx(5.0)


def test_random_curve_uses_exact_combinatorics() -> None:
    """구현이 근사식으로 바뀌지 않았는지 확인 (조합 정확값과 비교)."""
    table = {i: frozenset({"a"}) for i in range(3)}
    pool = list(range(10))
    curve = random_curve(table, pool, ["a"], max_budget=5)
    expected = [1.0 - math.comb(7, k) / math.comb(10, k) for k in range(1, 6)]
    assert curve == pytest.approx(expected)
