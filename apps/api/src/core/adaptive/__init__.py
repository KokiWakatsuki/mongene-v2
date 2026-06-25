"""適応学習エンジン（個別最適化 × 完全習得学習）。

責務分割:
  * ability_mapping … 習熟状況 → target_difficulty(1-100) の写像（ZPD + form_range クリップ）
  * mastery        … 採点結果 → 習熟状態の更新と習得判定（完全習得ゲート）
  * engine         … 前提グラフ + 習熟状態 → 次に出す ProblemGenerationRequest の決定
"""
from __future__ import annotations

from apps.api.src.core.adaptive.ability_mapping import recent_accuracy, target_difficulty_for
from apps.api.src.core.adaptive.mastery import (
    MASTERY_ACCURACY,
    MIN_ATTEMPTS,
    STREAK_TO_MASTER,
    update_mastery,
)
from apps.api.src.core.adaptive.engine import (
    NextDecision,
    NoLessonAvailableError,
    candidate_lessons,
    decide_next_lesson,
)

__all__ = [
    "recent_accuracy",
    "target_difficulty_for",
    "update_mastery",
    "MASTERY_ACCURACY",
    "MIN_ATTEMPTS",
    "STREAK_TO_MASTER",
    "NextDecision",
    "NoLessonAvailableError",
    "candidate_lessons",
    "decide_next_lesson",
]
