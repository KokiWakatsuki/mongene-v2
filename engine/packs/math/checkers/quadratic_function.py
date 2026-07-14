"""関数 y=ax² まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.evaluate_quadratic_function.double_solve")
def double_solve_evaluate_quadratic_function(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.evaluate_quadratic_function")
    return cast(Solution, solver(p["a"], p["x"]))


@register_checker("math.y_range_over_quadratic_domain.double_solve")
def double_solve_y_range_over_quadratic_domain(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.y_range_over_quadratic_domain")
    return cast(Solution, solver(p["a"], p["x_lo"], p["x_hi"], p["mode"]))


@register_checker("math.rate_of_change_quadratic.double_solve")
def double_solve_rate_of_change_quadratic(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.rate_of_change_quadratic")
    return cast(Solution, solver(p["a"], p["x1"], p["x2"], p["mode"]))


@register_checker("math.intersection_parabola_line.double_solve")
def double_solve_intersection_parabola_line(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.intersection_parabola_line")
    return cast(Solution, solver(p["a"], p["m"], p["b"], p["mode"]))


@register_checker("math.solve_quadratic_motion_area.double_solve")
def double_solve_solve_quadratic_motion_area(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.solve_quadratic_motion_area")
    return cast(Solution, solver(p["s"], p["d"], p["mode"]))


__all__ = [
    "double_solve_evaluate_quadratic_function",
    "double_solve_y_range_over_quadratic_domain",
    "double_solve_rate_of_change_quadratic",
    "double_solve_intersection_parabola_line",
    "double_solve_solve_quadratic_motion_area",
]
