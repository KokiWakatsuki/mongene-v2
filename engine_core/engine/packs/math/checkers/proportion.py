"""比例・反比例まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。

G-Q1 は `f"{mr.provenance.recipe}.double_solve"` で checker を引き、MR の params に残った
「問題を定義する値」だけから独立ソルバで解き直す。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.evaluate_direct_proportion.double_solve")
def double_solve_evaluate_direct_proportion(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.evaluate_direct_proportion")
    return cast(Solution, solver(mr.params["a"], mr.params["x0"], mr.params["mode"]))


@register_checker("math.evaluate_inverse_proportion.double_solve")
def double_solve_evaluate_inverse_proportion(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.evaluate_inverse_proportion")
    return cast(Solution, solver(mr.params["a"], mr.params["known"], mr.params["mode"]))


@register_checker("math.judge_functional_relation.double_solve")
def double_solve_judge_functional_relation(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.judge_functional_relation")
    return cast(Solution, solver(mr.params["is_functional"]))


@register_checker("math.judge_direct_proportion_table.double_solve")
def double_solve_judge_direct_proportion_table(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.judge_direct_proportion_table")
    return cast(Solution, solver(mr.params["xs"], mr.params["ys"]))


@register_checker("math.judge_inverse_proportion_table.double_solve")
def double_solve_judge_inverse_proportion_table(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.judge_inverse_proportion_table")
    return cast(Solution, solver(mr.params["xs"], mr.params["ys"]))


@register_checker("math.solve_direct_proportion_from_point.double_solve")
def double_solve_solve_direct_proportion_from_point(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.solve_direct_proportion_from_point")
    return cast(Solution, solver(mr.params["x0"], mr.params["y0"], mr.params["mode"]))


@register_checker("math.solve_inverse_proportion_from_point.double_solve")
def double_solve_solve_inverse_proportion_from_point(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.solve_inverse_proportion_from_point")
    return cast(Solution, solver(mr.params["x0"], mr.params["y0"], mr.params["mode"]))


@register_checker("math.judge_proportion_graph_direction.double_solve")
def double_solve_judge_proportion_graph_direction(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.judge_proportion_graph_direction")
    return cast(Solution, solver(mr.params["is_a_positive"]))


@register_checker("math.judge_hyperbola_quadrants.double_solve")
def double_solve_judge_hyperbola_quadrants(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.judge_hyperbola_quadrants")
    return cast(Solution, solver(mr.params["is_a_positive"]))
