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
    # 与式の文字列 expr_str と mode から独立に sympy で再評価する。
    p = mr.params
    solver = REGISTRY.solver("math.evaluate_numeric_expression")
    return cast(Solution, solver(p["expr_str"], p["mode"]))


__all__ = ["double_solve_compute_signed_arithmetic"]
