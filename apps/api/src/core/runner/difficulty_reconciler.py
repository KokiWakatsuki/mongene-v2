"""target_difficulty と y_base の調整（§39）"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, Optional

from apps.api.src.core.abc.blueprint import BlueprintDefinition

DELTA_MAX = 15


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
    raw_delta = target - y_base

    if -DELTA_MAX <= raw_delta <= DELTA_MAX:
        return DifficultyPlan(
            blueprint=blueprint,
            computed_difficulty=target,
            delta_factors=_distribute_delta(raw_delta, problem_form),
        )

    if raw_delta > DELTA_MAX:
        adjusted_blueprint = _make_advanced_variant(blueprint, target, y_base)
        delta_used = DELTA_MAX
        return DifficultyPlan(
            blueprint=adjusted_blueprint,
            computed_difficulty=y_base + delta_used,
            delta_factors=_distribute_delta(delta_used, problem_form),
            unsatisfiable=(target - y_base - delta_used > 20),
            reason=f"target={target} が y_base={y_base} と乖離。可能な最大: {y_base + delta_used}",
        )

    return DifficultyPlan(
        blueprint=blueprint,
        computed_difficulty=y_base - DELTA_MAX,
        delta_factors={"hint_reduction": -DELTA_MAX},
        unsatisfiable=False,
    )


def _distribute_delta(delta: int, problem_form: str) -> Dict[str, int]:
    factors: Dict[str, int] = {}
    remaining = delta
    if problem_form == "word_problem" and remaining < 0:
        factors["hint_reduction"] = max(remaining, -3)
        remaining -= factors["hint_reduction"]
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
