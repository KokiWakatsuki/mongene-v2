"""三平方の定理・その逆まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.pythagorean_hypotenuse.double_solve")
def double_solve_pythagorean_hypotenuse(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.pythagorean_hypotenuse")
    return cast(Solution, solver(p["leg_a"], p["leg_b"]))


@register_checker("math.identify_hypotenuse.double_solve")
def double_solve_identify_hypotenuse(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.identify_hypotenuse")
    return cast(Solution, solver(p["labels"], p["right_angle_index"]))


@register_checker("math.verify_right_triangle_from_sides.double_solve")
def double_solve_verify_right_triangle_from_sides(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.verify_right_triangle_from_sides")
    return cast(Solution, solver(p["side_a"], p["side_b"], p["side_c"]))


@register_checker("math.judge_right_triangle_from_three_sides.double_solve")
def double_solve_judge_right_triangle_from_three_sides(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_right_triangle_from_three_sides")
    return cast(Solution, solver(p["side_a"], p["side_b"], p["side_c"]))
