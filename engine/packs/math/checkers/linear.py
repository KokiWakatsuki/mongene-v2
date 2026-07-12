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


@register_checker("math.evaluate_linear_fraction.double_solve")
def double_solve_evaluate_linear_fraction(mr: MR) -> Solution:
    # 分数係数の代入も y=ax+b の x=x0 での値＝evaluate_linear_at_x を再利用（g2_l19 と共有）。
    p = mr.params
    solver = REGISTRY.solver("math.evaluate_linear_at_x")
    return cast(Solution, solver(
        sympy.sympify(p["a"]), sympy.sympify(p["b"]), sympy.sympify(p["x0"]),
    ))


@register_checker("math.draw_segment.double_solve")
def double_solve_draw_segment(mr: MR) -> Solution:
    # 問題パラメータ（a,b・変域端 x_lo/x_hi・開閉 closed_lo/closed_hi）だけから端点特徴を再計算。
    p = mr.params
    solver = REGISTRY.solver("math.draw_segment_features")
    return cast(Solution, solver(
        sympy.sympify(p["a"]), sympy.sympify(p["b"]),
        sympy.sympify(p["seg_x_lo"]), sympy.sympify(p["seg_x_hi"]),
        bool(p["closed_lo"]), bool(p["closed_hi"]),
    ))


@register_checker("math.draw_linear_fraction.double_solve")
def double_solve_draw_linear_fraction(mr: MR) -> Solution:
    # 問題パラメータ（分子 p・分母 q・切片 b）だけから特徴を再計算（GraphAnswer）。
    p = mr.params
    solver = REGISTRY.solver("math.draw_linear_features_fraction")
    return cast(Solution, solver(
        sympy.sympify(p["p"]), sympy.sympify(p["q"]), sympy.sympify(p["b"]),
    ))


@register_checker("math.draw_from_table.double_solve")
def double_solve_draw_from_table(mr: MR) -> Solution:
    # 対応表から作った線も y=ax+b の傾き・切片で採点＝draw_linear_features を再利用。
    p = mr.params
    solver = REGISTRY.solver("math.draw_linear_features")
    return cast(Solution, solver(sympy.sympify(p["a"]), sympy.sympify(p["b"])))


@register_checker("math.draw_special_lines.double_solve")
def double_solve_draw_special_lines(mr: MR) -> Solution:
    # 問題パラメータ（2交点 xi/yi と特殊直線 axis/k）だけから特徴を再計算（GraphAnswer）。
    p = mr.params
    solver = REGISTRY.solver("math.draw_special_lines")
    return cast(Solution, solver(
        sympy.sympify(p["xi"]), sympy.sympify(p["yi"]), p["axis"], sympy.sympify(p["k"]),
    ))


@register_checker("math.read_diagram_intersection.double_solve")
def double_solve_read_diagram_intersection(mr: MR) -> Solution:
    # ダイヤグラムの交点も 2直線の交点そのもの＝g2_l27 と同じ intersection solver を再利用。
    p = mr.params
    line_a = tuple(sympy.sympify(c) for c in p["line_a"])
    line_b = tuple(sympy.sympify(c) for c in p["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    return cast(Solution, solver(line_a, line_b, p["method"]))


@register_checker("math.solve_system_elimination.double_solve")
def double_solve_solve_system_elimination(mr: MR) -> Solution:
    p = mr.params
    line_a = tuple(sympy.sympify(c) for c in p["line_a"])
    line_b = tuple(sympy.sympify(c) for c in p["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    return cast(Solution, solver(line_a, line_b, p["method"]))


@register_checker("math.solve_system_substitution.double_solve")
def double_solve_solve_system_substitution(mr: MR) -> Solution:
    p = mr.params
    line_a = tuple(sympy.sympify(c) for c in p["line_a"])
    line_b = tuple(sympy.sympify(c) for c in p["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    return cast(Solution, solver(line_a, line_b, p["method"]))


@register_checker("math.solve_system_elim_scaled.double_solve")
def double_solve_solve_system_elim_scaled(mr: MR) -> Solution:
    p = mr.params
    line_a = tuple(sympy.sympify(c) for c in p["line_a"])
    line_b = tuple(sympy.sympify(c) for c in p["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    return cast(Solution, solver(line_a, line_b, p["method"]))


@register_checker("math.solve_system_preprocessed.double_solve")
def double_solve_solve_system_preprocessed(mr: MR) -> Solution:
    p = mr.params
    line_a = tuple(sympy.sympify(c) for c in p["line_a"])
    line_b = tuple(sympy.sympify(c) for c in p["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    return cast(Solution, solver(line_a, line_b, p["method"]))


@register_checker("math.solve_system_abc.double_solve")
def double_solve_solve_system_abc(mr: MR) -> Solution:
    p = mr.params
    line_a = tuple(sympy.sympify(c) for c in p["line_a"])
    line_b = tuple(sympy.sympify(c) for c in p["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    return cast(Solution, solver(line_a, line_b, p["method"]))


@register_checker("math.knowledge_slope_direction.double_solve")
def double_solve_knowledge_slope_direction(mr: MR) -> Solution:
    # 問題パラメータの傾き a だけから向き（ChoiceAnswer）を再判定（切片 b は無関係）。
    a = sympy.sympify(mr.params["a"])
    solver = REGISTRY.solver("math.linear_direction_from_slope")
    return cast(Solution, solver(a))


@register_checker("math.knowledge_classify_line_signs.double_solve")
def double_solve_knowledge_classify_line_signs(mr: MR) -> Solution:
    # 傾き a・切片 b の符号だけから4分類を再判定（式の値は無関係）。
    p = mr.params
    solver = REGISTRY.solver("math.classify_line_by_signs")
    return cast(Solution, solver(sympy.sympify(p["a"]), sympy.sympify(p["b"])))


@register_checker("math.knowledge_range_endpoint.double_solve")
def double_solve_knowledge_range_endpoint(mr: MR) -> Solution:
    # 包含は不等号の等号の有無（inclusive）だけから再判定（端点値・関数は無関係）。
    solver = REGISTRY.solver("math.range_endpoint_inclusion")
    return cast(Solution, solver(bool(mr.params["inclusive"])))


@register_checker("math.knowledge_verify_solution.double_solve")
def double_solve_knowledge_verify_solution(mr: MR) -> Solution:
    p = mr.params
    line_a = tuple(sympy.sympify(c) for c in p["line_a"])
    line_b = tuple(sympy.sympify(c) for c in p["line_b"])
    cand = sympy.sympify(p["candidate"])  # "(x, y)" -> sympy Tuple
    solver = REGISTRY.solver("math.verify_system_solution")
    return cast(Solution, solver(line_a, line_b, (cand[0], cand[1])))


@register_checker("math.knowledge_classify_linear.double_solve")
def double_solve_knowledge_classify_linear(mr: MR) -> Solution:
    # 問題パラメータの式 rhs だけから1次関数か再判定（category ビットは見ない）。
    rhs = sympy.sympify(mr.params["rhs"])
    solver = REGISTRY.solver("math.classify_linear_function")
    return cast(Solution, solver(rhs))


@register_checker("math.linear_slope_as_rate.double_solve")
def double_solve_linear_slope_as_rate(mr: MR) -> Solution:
    # 傾き a だけから変化の割合（＝a）を再計算（切片 b は無関係）。
    a = sympy.sympify(mr.params["a"])
    solver = REGISTRY.solver("math.linear_slope_as_rate")
    return cast(Solution, solver(a))


@register_checker("math.knowledge_coefficient_role.double_solve")
def double_solve_knowledge_coefficient_role(mr: MR) -> Solution:
    # which（係数/定数項）だけから傾き/切片を再判定（式の値は無関係）。
    solver = REGISTRY.solver("math.linear_coefficient_role")
    return cast(Solution, solver(mr.params["which"]))


@register_checker("math.knowledge_rate_constant.double_solve")
def double_solve_knowledge_rate_constant(mr: MR) -> Solution:
    # 変化の割合の性質は式によらず不変（答え固定型）。solver は引数を取らない。
    solver = REGISTRY.solver("math.rate_of_change_is_constant")
    return cast(Solution, solver())


@register_checker("math.knowledge_equation_solution_set.double_solve")
def double_solve_knowledge_equation_solution_set(mr: MR) -> Solution:
    # 解の集合は直線（係数によらず不変・答え固定型）。solver は引数を取らない。
    solver = REGISTRY.solver("math.equation_solution_set_shape")
    return cast(Solution, solver())


@register_checker("math.knowledge_system_intersection.double_solve")
def double_solve_knowledge_system_intersection(mr: MR) -> Solution:
    # 連立の解は2直線の交点（係数によらず不変・答え固定型）。solver は引数を取らない。
    solver = REGISTRY.solver("math.system_solution_is_intersection")
    return cast(Solution, solver())


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
    "double_solve_read_diagram_intersection",
    "double_solve_draw_special_lines",
    "double_solve_draw_from_table",
    "double_solve_draw_linear_fraction",
    "double_solve_draw_segment",
    "double_solve_evaluate_linear_fraction",
    "double_solve_solve_system_elimination",
    "double_solve_solve_system_substitution",
    "double_solve_solve_system_elim_scaled",
    "double_solve_solve_system_preprocessed",
    "double_solve_solve_system_abc",
    "double_solve_knowledge_slope_direction",
    "double_solve_knowledge_classify_line_signs",
    "double_solve_knowledge_range_endpoint",
    "double_solve_knowledge_verify_solution",
    "double_solve_knowledge_classify_linear",
    "double_solve_linear_slope_as_rate",
    "double_solve_knowledge_coefficient_role",
    "double_solve_knowledge_rate_constant",
    "double_solve_knowledge_equation_solution_set",
    "double_solve_knowledge_system_intersection",
    "double_solve_rate_of_change",
    "double_solve_intersection",
    "double_solve_y_range",
    "double_solve_expr_from_range",
]
