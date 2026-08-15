"""y=ax² の graph_table（かく／読む）の double_solve checker（G-Q1 が呼ぶ・§6.2）。

checker は MR.params だけを見て独立に再計算する（recipe の中間値は見ない）。
「読む」セルは params に残した場面パラメータ（比例定数・長方形の2辺・読み取る時刻）
から点の座標を組み立て直してから solver を呼ぶ＝座標そのものを params に置かない。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker
from engine.packs.math.recipes.quadratic_function_graph import _rect_area_at


@register_checker("math.read_two_points_on_parabola.double_solve")
def double_solve_read_two_points_on_parabola(mr: MR) -> Solution:
    p = mr.params
    a = sympy.sympify(p["coeff"])
    x1, x2 = sympy.Integer(p["x1"]), sympy.Integer(p["x2"])
    solver = REGISTRY.solver("math.read_two_lattice_points")
    return cast(Solution, solver((x1, a * x1**2), (x2, a * x2**2)))


@register_checker("math.draw_two_parabolas.double_solve")
def double_solve_draw_two_parabolas(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.draw_two_parabolas_features")
    return cast(Solution, solver(
        sympy.sympify(p["coeff"]), sympy.sympify(p["coeff2"]), p["table_lo"], p["table_hi"],
    ))


@register_checker("math.draw_parabola_domain.double_solve")
def double_solve_draw_parabola_domain(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.draw_parabola_domain_features")
    return cast(Solution, solver(sympy.sympify(p["coeff"]), p["arc_x_lo"], p["arc_x_hi"]))


@register_checker("math.draw_phenomenon_curve.double_solve")
def double_solve_draw_phenomenon_curve(mr: MR) -> Solution:
    p = mr.params
    step, rows = int(p["step"]), int(p["rows"])
    # 図形の場面は x=1 から始まる（1辺 0cm の正方形は図形にならない）。
    x_from = int(p.get("x_from", 0))
    xs = [step * i for i in range(x_from, rows + 1)]
    solver = REGISTRY.solver("math.draw_quantity_curve_features")
    return cast(Solution, solver(sympy.sympify(p["coeff"]), xs))


@register_checker("math.draw_parabola_and_line.double_solve")
def double_solve_draw_parabola_and_line(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.draw_parabola_line_features")
    return cast(Solution, solver(
        sympy.sympify(p["coeff"]), sympy.sympify(p["line_m"]), sympy.sympify(p["line_b"]),
    ))


@register_checker("math.read_area_time_graph.double_solve")
def double_solve_read_area_time_graph(mr: MR) -> Solution:
    p = mr.params
    p_side, q_side = int(p["side_p"]), int(p["side_q"])
    t1, t2 = int(p["t1"]), int(p["t2"])
    solver = REGISTRY.solver("math.read_two_lattice_points")
    return cast(Solution, solver(
        (sympy.Integer(t1), _rect_area_at(p_side, q_side, t1)),
        (sympy.Integer(t2), _rect_area_at(p_side, q_side, t2)),
    ))


@register_checker("math.draw_piecewise_area_graph.double_solve")
def double_solve_draw_piecewise_area_graph(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.draw_piecewise_area_graph_features")
    return cast(Solution, solver(p["side"], p["speed"]))


__all__ = [
    "double_solve_read_two_points_on_parabola",
    "double_solve_draw_two_parabolas",
    "double_solve_draw_parabola_domain",
    "double_solve_draw_phenomenon_curve",
    "double_solve_draw_parabola_and_line",
    "double_solve_read_area_time_graph",
    "double_solve_draw_piecewise_area_graph",
]
