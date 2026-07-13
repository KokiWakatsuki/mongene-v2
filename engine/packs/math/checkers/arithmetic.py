"""正の数・負の数の四則まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。

G-Q1 は `f"{mr.provenance.recipe}.double_solve"` で checker を引き、MR の params に残った
「問題を定義する値」（与式の文字列 expr_str と mode）だけから独立ソルバで解き直す。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.compute_signed_arithmetic.double_solve")
def double_solve_compute_signed_arithmetic(mr: MR) -> Solution:
    # mode により独立ソルバを使い分ける。
    #  order_numbers: numbers_str + ascending を並べ替えソルバで再計算。
    #  それ以外     : 与式の文字列 expr_str を数値評価ソルバで再計算。
    p = mr.params
    if p["mode"] == "order_numbers":
        solver = REGISTRY.solver("math.order_signed_numbers")
        return cast(Solution, solver(p["numbers_str"], p["ascending"]))
    solver = REGISTRY.solver("math.evaluate_numeric_expression")
    return cast(Solution, solver(p["expr_str"], p["mode"]))


@register_checker("math.factorize_integer.double_solve")
def double_solve_factorize_integer(mr: MR) -> Solution:
    # 対象数 value と mode から独立に素因数分解し直す（srepr の一致で G-Q1 が判定）。
    p = mr.params
    solver = REGISTRY.solver("math.factorize_integer")
    return cast(Solution, solver(p["value"], p["mode"]))


__all__ = ["double_solve_compute_signed_arithmetic", "double_solve_factorize_integer"]
