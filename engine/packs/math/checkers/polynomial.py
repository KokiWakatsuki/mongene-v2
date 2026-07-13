"""多項式（式の計算）まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。

G-Q1 は `f"{mr.provenance.recipe}.double_solve"` という名前で checker を引き、
MR から独立に答えを再計算した `Solution` を得て、MR の小問 answer と一致するか
検査する。ここでの独立性の要諦は「recipe が MR.params に残した『問題を定義する値』
（項の係数・文字の並び）だけ」から、Task5a 相当の登録済みソルバで解き直すこと。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


def _expr_str_from_params(mr: MR) -> str:
    """params の "terms": [[coef_str, var], ...] から solver への独立入力文字列を復元する。"""
    terms = mr.params["terms"]
    parts = []
    for coef_str, var in terms:
        parts.append(f"({coef_str})*{var}" if var else f"({coef_str})")
    return "+".join(parts)


@register_checker("math.combine_like_terms.double_solve")
def double_solve_combine_like_terms(mr: MR) -> Solution:
    expr_str = _expr_str_from_params(mr)
    solver = REGISTRY.solver("math.simplify_polynomial")
    return cast(Solution, solver(expr_str))


@register_checker("math.add_or_subtract_polynomials.double_solve")
def double_solve_add_or_subtract_polynomials(mr: MR) -> Solution:
    # 与式の文字列 expr_str と加減の別（is_subtraction）から独立に expand で再計算。
    p = mr.params
    solver = REGISTRY.solver("math.add_or_subtract_polynomials")
    return cast(Solution, solver(p["expr_str"], p["is_subtraction"]))


@register_checker("math.distribute_or_divide.double_solve")
def double_solve_distribute_or_divide(mr: MR) -> Solution:
    # 与式の文字列 expr_str と乗除の別（is_division）から独立に expand で再計算。
    p = mr.params
    solver = REGISTRY.solver("math.distribute_or_divide")
    return cast(Solution, solver(p["expr_str"], p["is_division"]))


@register_checker("math.compute_monomial_expression.double_solve")
def double_solve_compute_monomial_expression(mr: MR) -> Solution:
    # 与式の文字列 expr_str と mode（steps op 列の別）から独立に sympy で再計算。
    p = mr.params
    solver = REGISTRY.solver("math.compute_monomial_expression")
    return cast(Solution, solver(p["expr_str"], p["mode"]))


@register_checker("math.combine_fractional_expressions.double_solve")
def double_solve_combine_fractional_expressions(mr: MR) -> Solution:
    # 与式の文字列 expr_str と mode から独立に sympy.together で再計算。
    p = mr.params
    solver = REGISTRY.solver("math.combine_fractional_expressions")
    return cast(Solution, solver(p["expr_str"], p["mode"]))


@register_checker("math.degree_of_expression.double_solve")
def double_solve_degree_of_expression(mr: MR) -> Solution:
    # 与式の文字列 expr_str から独立に sympy.degree で次数を再計算。
    p = mr.params
    solver = REGISTRY.solver("math.degree_of_expression")
    return cast(Solution, solver(p["expr_str"]))


@register_checker("math.solve_for_variable.double_solve")
def double_solve_solve_for_variable(mr: MR) -> Solution:
    # 与式 equation_str・target・mode から独立に sympy.solve で再計算。
    p = mr.params
    solver = REGISTRY.solver("math.solve_for_variable")
    return cast(Solution, solver(p["equation_str"], p["target"], p["mode"]))


@register_checker("math.express_number_property.double_solve")
def double_solve_express_number_property(mr: MR) -> Solution:
    # 与式 expr_str（各数を表す式の和）から独立に sympy.expand で再計算。
    p = mr.params
    solver = REGISTRY.solver("math.express_number_property")
    return cast(Solution, solver(p["expr_str"]))


@register_checker("math.combine_digit_number.double_solve")
def double_solve_combine_digit_number(mr: MR) -> Solution:
    # 与式 expr_str と operation から独立に sympy.expand で再計算。
    p = mr.params
    solver = REGISTRY.solver("math.combine_digit_number")
    return cast(Solution, solver(p["expr_str"], p["operation"]))


@register_checker("math.poly_term_recall.double_solve")
def double_solve_poly_term_recall(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.poly_term_definition")
    return cast(Solution, solver(mr.params["concept"]))


@register_checker("math.classify_monomial_or_polynomial.double_solve")
def double_solve_classify_monomial_or_polynomial(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.classify_monomial_or_polynomial")
    return cast(Solution, solver(mr.params["expr_str"]))


@register_checker("math.judge_like_terms.double_solve")
def double_solve_judge_like_terms(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_like_terms")
    return cast(Solution, solver(p["term1"], p["term2"]))


@register_checker("math.system_term_recall.double_solve")
def double_solve_system_term_recall(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.system_term_definition")
    return cast(Solution, solver(mr.params["concept"]))


@register_checker("math.expand_product.double_solve")
def double_solve_expand_product(mr: MR) -> Solution:
    # 与式の文字列 expr_str と mode（steps op 列の別）から独立に sympy.expand で再計算。
    p = mr.params
    solver = REGISTRY.solver("math.expand_expression")
    return cast(Solution, solver(p["expr_str"], p["mode"]))


__all__ = [
    "double_solve_combine_like_terms",
    "double_solve_add_or_subtract_polynomials",
    "double_solve_distribute_or_divide",
    "double_solve_compute_monomial_expression",
    "double_solve_combine_fractional_expressions",
    "double_solve_degree_of_expression",
    "double_solve_solve_for_variable",
    "double_solve_express_number_property",
    "double_solve_combine_digit_number",
    "double_solve_poly_term_recall",
    "double_solve_classify_monomial_or_polynomial",
    "double_solve_judge_like_terms",
    "double_solve_system_term_recall",
    "double_solve_expand_product",
]
