"""target_difficulty と y_base の調整（§39）

問題形式ごとの有効難易度レンジ（§12.4 hint_reduction / proof_complexity より）:

  calculation  : y_base - 15 ≤ target ≤ y_base + 13  （図あり → hint_reduction=-2 で実効上限低め）
  word_problem : y_base - 12 ≤ target ≤ y_base + 15  （文章のみ → hint_reduction=+3 で難しい）
  proof        : y_base + 3  ≤ target ≤ y_base + 15  （証明 → proof_complexity=+3 で常に高め）
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from apps.api.src.core.abc.blueprint import BlueprintDefinition

DELTA_MAX = 15

# 問題形式別の delta 上下限（§12.4）
# (delta_min, delta_max)
FORM_DELTA_RANGE: Dict[str, Tuple[int, int]] = {
    # 計算問題: 数値・式が全部与えられ「計算するだけ」→ 狭い範囲
    # 例: 「次を計算しなさい: √48 ÷ √3」「次の方程式を解け」
    "calculation": (-5, 5),
    # 文章題: 場面を読んで式を立てる必要がある → 計算問題より広く難しくなれる
    "word_problem": (-5, 15),
    # 証明: 論理的推論が必要で常に一定の難しさがある
    "proof": (3, 15),
}


def get_form_range(y_base: int, problem_form: str) -> Tuple[int, int]:
    """問題形式に応じた (min_difficulty, max_difficulty) を返す"""
    d_min, d_max = FORM_DELTA_RANGE.get(problem_form, (-DELTA_MAX, DELTA_MAX))
    return max(1, y_base + d_min), min(100, y_base + d_max)


@dataclass
class DifficultyPlan:
    blueprint: BlueprintDefinition
    computed_difficulty: int
    delta_factors: Dict[str, int] = field(default_factory=dict)
    unsatisfiable: bool = False
    reason: Optional[str] = None


def reconcile_difficulty(
    target: int,
    y_base: int,
    blueprint: BlueprintDefinition,
    problem_form: str,
) -> DifficultyPlan:
    d_min, d_max = get_form_range(y_base, problem_form)
    delta_lo = d_min - y_base
    delta_hi = d_max - y_base

    raw_delta = target - y_base
    clamped_delta = max(delta_lo, min(delta_hi, raw_delta))

    if raw_delta <= delta_hi:
        return DifficultyPlan(
            blueprint=blueprint,
            computed_difficulty=y_base + clamped_delta,
            delta_factors=_distribute_delta(clamped_delta, problem_form),
        )

    # target が形式の上限を超える場合
    adjusted_blueprint = _make_advanced_variant(blueprint, target, y_base)
    return DifficultyPlan(
        blueprint=adjusted_blueprint,
        computed_difficulty=y_base + delta_hi,
        delta_factors=_distribute_delta(delta_hi, problem_form),
        unsatisfiable=(raw_delta - delta_hi > 20),
        reason=f"target={target} が {problem_form} の上限 {y_base + delta_hi} を超過",
    )


def _distribute_delta(delta: int, problem_form: str) -> Dict[str, int]:
    """§12.4 の delta ファクター分配"""
    factors: Dict[str, int] = {}
    remaining = delta

    # 問題形式固有のベースファクター
    if problem_form == "calculation":
        factors["hint_reduction"] = -2  # 図あり → 実効難易度を下げる
        remaining += 2  # hint_reduction 分の余裕
    elif problem_form == "word_problem":
        factors["hint_reduction"] = 3   # 文章のみ → 実効難易度を上げる
        remaining -= 3
    elif problem_form == "proof":
        factors["proof_complexity"] = 3  # 証明の複雑さ
        remaining -= 3

    if remaining > 0:
        factors["digit_penalty"] = min(remaining, 3)
        remaining -= factors["digit_penalty"]
        if remaining > 0:
            factors["step_depth"] = min(remaining, 5)
            remaining -= factors["step_depth"]
    if remaining != 0:
        factors["unit_mix_bonus"] = remaining

    return factors


def _make_advanced_variant(
    blueprint: BlueprintDefinition,
    target: int,
    y_base: int,
) -> BlueprintDefinition:
    if blueprint.subquestion_strategy is None:
        return blueprint
    enhanced = copy.deepcopy(blueprint)
    enhanced.subquestion_strategy.strategy_type = "incremental"  # type: ignore[union-attr]
    enhanced.subquestion_strategy.target_count = min(  # type: ignore[union-attr]
        enhanced.subquestion_strategy.target_count + 2, 5  # type: ignore[union-attr]
    )
    return enhanced
