"""習熟更新・完全習得ゲートのテスト。"""
from __future__ import annotations

from apps.api.src.core.adaptive.mastery import MIN_ATTEMPTS, update_mastery
from apps.api.src.core.store.models import MasteryState


def _fresh() -> MasteryState:
    return MasteryState(student_id="s1", lesson_id="g1_l1")


def test_first_attempt_sets_attempted() -> None:
    s = update_mastery(_fresh(), True)
    assert s.attempted is True
    assert s.attempt_count == 1
    assert s.correct_streak == 1


def test_wrong_resets_streak() -> None:
    s = _fresh()
    update_mastery(s, True)
    update_mastery(s, True)
    assert s.correct_streak == 2
    update_mastery(s, False)
    assert s.correct_streak == 0
    assert s.mastered is False


def test_not_mastered_before_min_attempts() -> None:
    s = _fresh()
    # 3 連続正答でも試行数が MIN_ATTEMPTS 未満なら未習得
    for _ in range(3):
        update_mastery(s, True)
    assert s.attempt_count == 3 < MIN_ATTEMPTS
    assert s.mastered is False


def test_mastered_after_five_consecutive_correct() -> None:
    s = _fresh()
    for _ in range(5):
        update_mastery(s, True)
    assert s.attempt_count == 5
    assert s.correct_streak == 5
    assert s.mastery == 1.0
    assert s.mastered is True


def test_window_bounds_recent_accuracy() -> None:
    s = _fresh()
    # 古い不正解はウィンドウ(5)から押し出される
    update_mastery(s, False)
    for _ in range(5):
        update_mastery(s, True)
    # 直近5問は全て正解 → accuracy 1.0、streak 5、試行6 → 習得
    assert s.recent_window == [True, True, True, True, True]
    assert s.mastered is True
