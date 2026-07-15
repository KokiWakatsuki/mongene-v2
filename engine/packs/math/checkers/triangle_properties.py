"""三角形の合同条件・二等辺三角形・正三角形まわりの double_solve checker

（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.isosceles_base_angle.double_solve")
def double_solve_isosceles_base_angle(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.isosceles_base_angle")
    return cast(Solution, solver(p["known_type"], p["known_value"]))


@register_checker("math.equilateral_triangle_properties.double_solve")
def double_solve_equilateral_triangle_properties(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.equilateral_triangle_properties")
    return cast(Solution, solver(p["side"]))


@register_checker("math.judge_isosceles_from_angle_condition.double_solve")
def double_solve_judge_isosceles_from_angle_condition(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_isosceles_from_angle_condition")
    return cast(Solution, solver(p["is_equal"]))


@register_checker("math.judge_equilateral_from_condition.double_solve")
def double_solve_judge_equilateral_from_condition(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_equilateral_from_condition")
    return cast(Solution, solver(p["is_equilateral"]))
