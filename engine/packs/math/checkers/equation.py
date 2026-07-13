"""一次方程式まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。

G-Q1 は `f"{mr.provenance.recipe}.double_solve"` で checker を引き、MR の params に残った
「問題を定義する値」（方程式の文字列 equation_str と mode）だけから独立ソルバで解き直す。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.compute_linear_equation.double_solve")
def double_solve_compute_linear_equation(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.solve_linear_equation")
    return cast(Solution, solver(mr.params["equation_str"], mr.params["mode"]))


__all__ = ["double_solve_compute_linear_equation"]
