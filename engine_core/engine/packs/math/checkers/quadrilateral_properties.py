"""平行四辺形・特別な平行四辺形・等積変形まわりの double_solve checker

（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.parallelogram_opposite_properties.double_solve")
def double_solve_parallelogram_opposite_properties(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.parallelogram_opposite_properties")
    return cast(Solution, solver(p["side_value"], p["angle_value"]))


@register_checker("math.identify_parallelogram_condition.double_solve")
def double_solve_identify_parallelogram_condition(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.identify_parallelogram_condition")
    return cast(Solution, solver(p["condition_key"]))


@register_checker("math.special_parallelogram_diagonal_value.double_solve")
def double_solve_special_parallelogram_diagonal_value(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.special_parallelogram_diagonal_value")
    return cast(Solution, solver(p["shape"], p["value"]))


@register_checker("math.classify_quadrilateral_from_diagonal_condition.double_solve")
def double_solve_classify_quadrilateral_from_diagonal_condition(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.classify_quadrilateral_from_diagonal_condition")
    return cast(Solution, solver(p["equal"], p["perpendicular"]))


@register_checker("math.equal_area_transform_value.double_solve")
def double_solve_equal_area_transform_value(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.equal_area_transform_value")
    return cast(Solution, solver(p["area_value"]))
