"""double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。

G-Q1 は `f"{mr.provenance.recipe}.double_solve"` という名前で checker を引き、
MR から独立に答えを再計算した `Solution` を得て、MR の小問 answer と一致するか
検査する。ここでの独立性の要諦は「**recipe が MR.params に残した『問題を定義する値』
（2点・傾き・通る点）だけ**から、Task5a の登録済みソルバで解き直す」こと。recipe が
構成した answer 値（a/b から作った式）は参照しない。

recipe と checker が同じソルバを使うのは冗長に見えるが、G-Q1 は generate の**ゲート段**
で MR を独立入力として再検算する関門であり、recipe 内 assert（構成直後の自己検査）とは
別レイヤの担保である（H5）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


def _parse_point(s: str) -> tuple[object, object]:
    """params に str で残した点 "(x, y)" を sympy で復元して (x, y) タプルにする。"""
    t = sympy.sympify(s)
    return (t[0], t[1])


@register_checker("math.linear_from_two_points.double_solve")
def double_solve_two_points(mr: MR) -> Solution:
    p = mr.params
    p1 = _parse_point(p["pts"][0])
    p2 = _parse_point(p["pts"][1])
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    return cast(Solution, solver(p1, p2, p["method"]))


@register_checker("math.linear_from_slope_point.double_solve")
def double_solve_slope_point(mr: MR) -> Solution:
    p = mr.params
    slope = sympy.sympify(p["a"])
    point = _parse_point(p["point"])
    solver = REGISTRY.solver("math.linear_expr_from_slope_point")
    return cast(Solution, solver(slope, point))


@register_checker("math.linear_from_parallel_condition.double_solve")
def double_solve_parallel(mr: MR) -> Solution:
    p = mr.params
    parallel_slope = sympy.sympify(p["a"])
    point = _parse_point(p["point"])
    solver = REGISTRY.solver("math.linear_expr_parallel_through_point")
    return cast(Solution, solver(parallel_slope, point))


@register_checker("math.graph_read_two_points.double_solve")
def double_solve_graph_read(mr: MR) -> Solution:
    p = mr.params
    p1 = _parse_point(p["pts"][0])
    p2 = _parse_point(p["pts"][1])
    solver = REGISTRY.solver("math.read_two_lattice_points")
    return cast(Solution, solver(p1, p2))


@register_checker("math.read_slope_intercept.double_solve")
def double_solve_read_slope_intercept(mr: MR) -> Solution:
    p = mr.params
    p1 = _parse_point(p["pts"][0])
    p2 = _parse_point(p["pts"][1])
    solver = REGISTRY.solver("math.read_slope_intercept_from_graph")
    return cast(Solution, solver(p1, p2))


@register_checker("math.solve_equation_for_y.double_solve")
def double_solve_solve_for_y(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.solve_equation_for_y")
    return cast(Solution, solver(
        sympy.sympify(p["a"]), sympy.sympify(p["b"]), sympy.sympify(p["c"]),
    ))


@register_checker("math.evaluate_linear.double_solve")
def double_solve_evaluate_linear(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.evaluate_linear_at_x")
    return cast(Solution, solver(
        sympy.sympify(p["a"]), sympy.sympify(p["b"]), sympy.sympify(p["x0"]),
    ))


@register_checker("math.point_on_line.double_solve")
def double_solve_point_on_line(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.point_on_line_at_x")
    return cast(Solution, solver(
        sympy.sympify(p["a"]), sympy.sympify(p["b"]), sympy.sympify(p["x0"]),
    ))


@register_checker("math.draw_linear.double_solve")
def double_solve_draw_linear(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.draw_linear_features")
    return cast(Solution, solver(sympy.sympify(p["a"]), sympy.sympify(p["b"])))


@register_checker("math.draw_linear_from_equation.double_solve")
def double_solve_draw_from_equation(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.draw_from_equation")
    return cast(Solution, solver(
        sympy.sympify(p["eq_a"]), sympy.sympify(p["eq_b"]), sympy.sympify(p["eq_c"]),
    ))


@register_checker("math.read_intersection_from_graph.double_solve")
def double_solve_read_intersection(mr: MR) -> Solution:
    p = mr.params
    line_a = tuple(sympy.sympify(c) for c in p["line_a"])
    line_b = tuple(sympy.sympify(c) for c in p["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    return cast(Solution, solver(line_a, line_b, p["method"]))


@register_checker("math.rate_of_change.double_solve")
def double_solve_rate_of_change(mr: MR) -> Solution:
    p = mr.params
    p1 = _parse_point(p["pts"][0])
    p2 = _parse_point(p["pts"][1])
    solver = REGISTRY.solver("math.rate_of_change_from_two_points")
    return cast(Solution, solver(p1, p2))


@register_checker("math.intersection.double_solve")
def double_solve_intersection(mr: MR) -> Solution:
    p = mr.params
    line_a = tuple(sympy.sympify(c) for c in p["line_a"])
    line_b = tuple(sympy.sympify(c) for c in p["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    return cast(Solution, solver(line_a, line_b, p["method"]))


@register_checker("math.y_range_from_domain.double_solve")
def double_solve_y_range(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.y_range_over_domain")
    return cast(Solution, solver(
        sympy.sympify(p["a"]), sympy.sympify(p["b"]),
        sympy.sympify(p["x_lo"]), sympy.sympify(p["x_hi"]),
    ))


@register_checker("math.expr_from_range.double_solve")
def double_solve_expr_from_range(mr: MR) -> Solution:
    p = mr.params
    p1 = _parse_point(p["pts"][0])
    p2 = _parse_point(p["pts"][1])
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    return cast(Solution, solver(p1, p2, p["method"]))


__all__ = [
    "double_solve_two_points",
    "double_solve_slope_point",
    "double_solve_parallel",
    "double_solve_graph_read",
    "double_solve_read_slope_intercept",
    "double_solve_solve_for_y",
    "double_solve_evaluate_linear",
    "double_solve_point_on_line",
    "double_solve_draw_linear",
    "double_solve_draw_from_equation",
    "double_solve_read_intersection",
    "double_solve_rate_of_change",
    "double_solve_intersection",
    "double_solve_y_range",
    "double_solve_expr_from_range",
]
