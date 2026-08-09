"""文字式（一次式の計算）まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。

G-Q1 は `f"{mr.provenance.recipe}.double_solve"` で checker を引き、MR の params に残った
「問題を定義する値」（与式の文字列 expr_str と mode）だけから独立ソルバで解き直す。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.compute_letter_expression.double_solve")
def double_solve_compute_letter_expression(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.evaluate_letter_expression")
    return cast(Solution, solver(mr.params["expr_str"], mr.params["mode"]))


@register_checker("math.compute_substitution.double_solve")
def double_solve_compute_substitution(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.evaluate_substitution")
    return cast(Solution, solver(mr.params["expr_str"], mr.params["subs_str"], mr.params["mode"]))


@register_checker("math.compute_notation.double_solve")
def double_solve_compute_notation(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.simplify_notation")
    return cast(Solution, solver(mr.params["expr_str"], mr.params["mode"]))


@register_checker("math.term_recall.double_solve")
def double_solve_term_recall(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.term_recall_definition")
    return cast(Solution, solver(mr.params["concept"], mr.params["domain"]))


@register_checker("math.verify_equation_solution.double_solve")
def double_solve_verify_equation_solution(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.verify_equation_solution")
    return cast(Solution, solver(mr.params["equation_str"], mr.params["value"]))


@register_checker("math.compare_signed_numbers.double_solve")
def double_solve_compare_signed_numbers(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.compare_signed_numbers")
    return cast(Solution, solver(mr.params["a"], mr.params["b"]))


@register_checker("math.recall_rule.double_solve")
def double_solve_recall_rule(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.recall_rule_statement")
    return cast(
        Solution,
        solver(mr.params["topic"], mr.params["concept"], mr.params.get("labels")),
    )


@register_checker("math.classify_number_sign.double_solve")
def double_solve_classify_number_sign(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.classify_number_sign")
    return cast(Solution, solver(mr.params["value"]))


@register_checker("math.represent_opposite_quantity.double_solve")
def double_solve_represent_opposite_quantity(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.represent_opposite_quantity")
    return cast(
        Solution,
        solver(mr.params["positive_label"], mr.params["asked_label"], mr.params["magnitude"]),
    )


@register_checker("math.judge_set_closure.double_solve")
def double_solve_judge_set_closure(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.judge_set_closure")
    return cast(Solution, solver(mr.params["number_set"], mr.params["operation"]))


@register_checker("math.count_significant_figures.double_solve")
def double_solve_count_significant_figures(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.count_significant_figures")
    return cast(Solution, solver(mr.params["measurement"]))


@register_checker("math.interpret_expression.double_solve")
def double_solve_interpret_expression(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.interpret_expression")
    return cast(Solution, solver(mr.params["item_a"], mr.params["item_b"]))


@register_checker("math.classify_rational_irrational.double_solve")
def double_solve_classify_rational_irrational(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.classify_rational_irrational")
    return cast(Solution, solver(mr.params["value_str"]))


@register_checker("math.verify_quadratic_solution.double_solve")
def double_solve_verify_quadratic_solution(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.verify_quadratic_solution")
    return cast(Solution, solver(mr.params["eq_str"], mr.params["value"]))


__all__ = [
    "double_solve_compute_letter_expression",
    "double_solve_compute_substitution",
    "double_solve_compute_notation",
    "double_solve_term_recall",
    "double_solve_verify_equation_solution",
    "double_solve_compare_signed_numbers",
    "double_solve_recall_rule",
    "double_solve_classify_number_sign",
    "double_solve_represent_opposite_quantity",
    "double_solve_judge_set_closure",
    "double_solve_count_significant_figures",
    "double_solve_interpret_expression",
    "double_solve_classify_rational_irrational",
    "double_solve_verify_quadratic_solution",
]
