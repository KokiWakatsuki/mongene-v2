"""平行線・三角形・多角形の角まわりの double_solve checker

（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.solve_angle_by_equality_relation.double_solve")
def double_solve_solve_angle_by_equality_relation(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.solve_angle_by_equality_relation")
    return cast(Solution, solver(p["relation"], p["angle"]))


@register_checker("math.solve_zigzag_angle_sum.double_solve")
def double_solve_solve_zigzag_angle_sum(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.solve_zigzag_angle_sum")
    return cast(Solution, solver(p["angle1"], p["angle2"]))


@register_checker("math.judge_parallel_from_angle_condition.double_solve")
def double_solve_judge_parallel_from_angle_condition(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_parallel_from_angle_condition")
    return cast(Solution, solver(p["is_equal"]))


@register_checker("math.triangle_third_angle.double_solve")
def double_solve_triangle_third_angle(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.triangle_third_angle")
    return cast(Solution, solver(p["angle_a"], p["angle_b"]))


@register_checker("math.polygon_interior_sum_and_angle.double_solve")
def double_solve_polygon_interior_sum_and_angle(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.polygon_interior_sum_and_angle")
    return cast(Solution, solver(p["sides"]))


@register_checker("math.polygon_sides_from_interior_sum.double_solve")
def double_solve_polygon_sides_from_interior_sum(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.polygon_sides_from_interior_sum")
    return cast(Solution, solver(p["interior_sum"]))


@register_checker("math.regular_polygon_exterior_angle.double_solve")
def double_solve_regular_polygon_exterior_angle(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.regular_polygon_exterior_angle")
    return cast(Solution, solver(p["sides"]))


@register_checker("math.polygon_sides_from_interior_angle.double_solve")
def double_solve_polygon_sides_from_interior_angle(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.polygon_sides_from_interior_angle")
    return cast(Solution, solver(p["interior_angle"]))
