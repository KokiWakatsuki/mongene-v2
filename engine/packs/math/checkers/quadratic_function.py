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


def _parabola_line_from_numbers(mr: MR) -> tuple[int, int, int]:
    """本文に出ている数値（比例定数 a・2点の x 座標）から m, b を導き直す。

    傾き m と切片 b は本文に出ていない導出値なので params には無い。checker 側で
    m=a(xA+xB), b=-a·xA·xB を組み直す＝recipe とは別経路で立式し直す。
    """
    n = mr.params["numbers"]
    a, xA, xB = int(n["a"]), int(n["x_a"]), int(n["x_b"])
    return a, a * (xA + xB), -a * xA * xB


@register_checker("math.word_problem_parabola_line_guided.double_solve")
def double_solve_word_problem_parabola_line_guided(mr: MR) -> list[Solution]:
    """(1)=直線ABの式・(2)=三角形OABの面積・(3)=等積になる点のx座標。"""
    n = mr.params["numbers"]
    a, xA, xB = int(n["a"]), int(n["x_a"]), int(n["x_b"])
    _a, m, b = _parabola_line_from_numbers(mr)
    return [
        cast(
            Solution,
            REGISTRY.solver("math.linear_expr_from_two_points")(
                (xA, a * xA**2), (xB, a * xB**2), "slope_then_intercept"
            ),
        ),
        cast(
            Solution,
            REGISTRY.solver("math.intersection_parabola_line")(a, m, b, "triangle_area"),
        ),
        cast(Solution, REGISTRY.solver("math.parabola_equal_area_point")(a, m, b)),
    ]


@register_checker("math.word_problem_parabola_area_ratio.double_solve")
def double_solve_word_problem_parabola_area_ratio(mr: MR) -> Solution:
    a, m, b = _parabola_line_from_numbers(mr)
    return cast(Solution, REGISTRY.solver("math.parabola_line_area_ratio")(a, m, b))


__all__ = [
    "double_solve_evaluate_quadratic_function",
    "double_solve_y_range_over_quadratic_domain",
    "double_solve_rate_of_change_quadratic",
    "double_solve_intersection_parabola_line",
    "double_solve_solve_quadratic_motion_area",
    "double_solve_word_problem_parabola_line_guided",
    "double_solve_word_problem_parabola_area_ratio",
]
