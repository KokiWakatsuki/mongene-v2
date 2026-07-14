"""2次方程式まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.solve_quadratic.double_solve")
def double_solve_solve_quadratic(mr: MR) -> Solution:
    # 与式 eq_str・mode・（evaluate 系のみ）value から独立に sympy.solve で解き直す。
    p = mr.params
    solver = REGISTRY.solver("math.solve_quadratic")
    return cast(Solution, solver(p["eq_str"], p["mode"], p.get("value")))


@register_checker("math.quadratic_rectangle_area_value.double_solve")
def double_solve_quadratic_rectangle_area_value(mr: MR) -> Solution:
    # 与式 eq_str・mode から独立に正の解のみを再計算する。
    p = mr.params
    solver = REGISTRY.solver("math.solve_quadratic")
    return cast(Solution, solver(p["eq_str"], p["mode"]))


__all__ = ["double_solve_solve_quadratic", "double_solve_quadratic_rectangle_area_value"]
