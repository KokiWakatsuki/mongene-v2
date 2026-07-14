"""動点まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.solve_moving_point_area.double_solve")
def double_solve_solve_moving_point_area(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.solve_moving_point_area")
    return cast(Solution, solver(p["s"], p["v"], p["t"], p["mode"]))


__all__ = ["double_solve_solve_moving_point_area"]
