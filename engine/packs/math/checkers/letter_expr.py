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


__all__ = [
    "double_solve_compute_letter_expression",
    "double_solve_compute_substitution",
    "double_solve_compute_notation",
    "double_solve_term_recall",
    "double_solve_verify_equation_solution",
]
