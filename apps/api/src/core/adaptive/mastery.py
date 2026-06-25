"""習熟状態の更新と完全習得ゲート（マスタリーラーニング）。

完全習得判定（提案システム設計の 3 条件 AND の MVP 版）:
  ① 直近ウィンドウの正答率 >= MASTERY_ACCURACY(0.8)
  ② 連続正答 >= STREAK_TO_MASTER(3)
  ③ 試行回数 >= MIN_ATTEMPTS(5)

後フェーズで ① を BKT の p_known>=0.85 に差し替え可能（I/F 不変）。
"""
from __future__ import annotations

from apps.api.src.core.store.models import MasteryState

WINDOW = 5              # 正答率を見る直近ウィンドウ幅
MASTERY_ACCURACY = 0.8  # 習得に必要な直近正答率
STREAK_TO_MASTER = 3    # 習得に必要な連続正答
MIN_ATTEMPTS = 5        # 習得に必要な最小試行数（少数試行での過信を防ぐ）


def update_mastery(state: MasteryState, is_correct: bool) -> MasteryState:
    """1 問の採点結果で習熟状態を更新する（破壊的に更新して返す）。"""
    state.attempted = True
    state.attempt_count += 1
    state.recent_window = (state.recent_window + [bool(is_correct)])[-WINDOW:]
    state.correct_streak = state.correct_streak + 1 if is_correct else 0

    accuracy = sum(1 for x in state.recent_window if x) / len(state.recent_window)
    state.mastery = accuracy
    state.mastered = (
        state.attempt_count >= MIN_ATTEMPTS
        and state.correct_streak >= STREAK_TO_MASTER
        and accuracy >= MASTERY_ACCURACY
    )
    return state
