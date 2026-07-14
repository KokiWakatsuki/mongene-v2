"""分数⇔循環小数の double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.convert_rational_decimal_form.double_solve")
def double_solve_convert_rational_decimal_form(mr: MR) -> Solution:
    p = mr.params
    mode = p["mode"]
    if mode == "fraction_to_repeating_decimal":
        solver = REGISTRY.solver("math.fraction_to_repeating_decimal")
        return cast(Solution, solver(p["p"], p["q"]))
    solver = REGISTRY.solver("math.repeating_decimal_to_fraction")
    return cast(Solution, solver(p["non_repeating"], p["repeating"]))


__all__ = ["double_solve_convert_rational_decimal_form"]
