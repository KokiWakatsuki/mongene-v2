"""能力→target_difficulty 写像（ZPD + form_range クリップ）のテスト。"""
from __future__ import annotations

from apps.api.src.core.adaptive.ability_mapping import recent_accuracy, target_difficulty_for
from apps.api.src.core.runner.difficulty_reconciler import get_form_range_from_y_base
from apps.api.src.core.store.models import MasteryState


def _state(window: list[bool]) -> MasteryState:
    return MasteryState(student_id="s1", lesson_id="g1_l5", recent_window=window)


def test_recent_accuracy_none_on_cold_start() -> None:
    assert recent_accuracy(_state([])) is None
    assert recent_accuracy(_state([True, False])) == 0.5


def test_cold_start_within_form_range() -> None:
    y_base, raw_y_base = 10, 300
    lo, hi = get_form_range_from_y_base(y_base, "calculation")
    t = target_difficulty_for(y_base, raw_y_base, "calculation", _state([]))
    assert lo <= t <= hi


def test_high_accuracy_harder_than_low_accuracy() -> None:
    y_base, raw_y_base = 10, 600
    high = target_difficulty_for(y_base, raw_y_base, "calculation", _state([True] * 5))
    low = target_difficulty_for(y_base, raw_y_base, "calculation", _state([False] * 5))
    assert high >= low


def test_difficulty_moves_with_performance() -> None:
    # 正答率が上がると難易度が上がる（個別最適化が動く最小証拠）
    y_base, raw_y_base = 12, 700
    cold = target_difficulty_for(y_base, raw_y_base, "calculation", _state([]))
    perfect = target_difficulty_for(y_base, raw_y_base, "calculation", _state([True] * 5))
    struggling = target_difficulty_for(y_base, raw_y_base, "calculation", _state([False] * 5))
    assert perfect >= cold >= struggling


def test_always_clipped_to_range() -> None:
    y_base, raw_y_base = 5, 150
    lo, hi = get_form_range_from_y_base(y_base, "calculation")
    for window in ([], [True] * 5, [False] * 5, [True, False, True]):
        t = target_difficulty_for(y_base, raw_y_base, "calculation", _state(window))
        assert lo <= t <= hi
