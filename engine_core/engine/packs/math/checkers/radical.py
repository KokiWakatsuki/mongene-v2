"""平方根まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.simplify_radical.double_solve")
def double_solve_simplify_radical(mr: MR) -> Solution:
    # 与式の文字列 expr_str と mode から独立に sympy で簡約し直す。
    p = mr.params
    solver = REGISTRY.solver("math.simplify_radical")
    return cast(Solution, solver(p["expr_str"], p["mode"]))


@register_checker("math.evaluate_radical_substitution.double_solve")
def double_solve_evaluate_radical_substitution(mr: MR) -> Solution:
    # 与式 expr_str・代入値 value_str(_y)・mode から独立に sympy.expand で代入し直す。
    # value_str_y は Lv3（2変数の対称式）のみ params に存在する。
    p = mr.params
    solver = REGISTRY.solver("math.evaluate_radical_substitution")
    return cast(
        Solution, solver(p["expr_str"], p["value_str"], p["mode"], p.get("value_str_y"))
    )


@register_checker("math.find_side_from_area.double_solve")
def double_solve_find_side_from_area(mr: MR) -> Solution:
    # 面積の式 expr_str だけから独立に √ を簡約し直す。
    p = mr.params
    solver = REGISTRY.solver("math.simplify_radical")
    return cast(Solution, solver(p["expr_str"], "find_side_from_area"))


@register_checker("math.compare_radical_values.double_solve")
def double_solve_compare_radical_values(mr: MR) -> Solution:
    # 構成した値のリスト exprs・mode だけから独立に大小を比較し直す。
    p = mr.params
    solver = REGISTRY.solver("math.compare_radical_values")
    return cast(Solution, solver(p["exprs"], p["mode"]))


__all__ = [
    "double_solve_simplify_radical", "double_solve_evaluate_radical_substitution",
    "double_solve_find_side_from_area", "double_solve_compare_radical_values",
]
