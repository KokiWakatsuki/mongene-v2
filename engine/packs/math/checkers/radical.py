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


__all__ = ["double_solve_simplify_radical"]
