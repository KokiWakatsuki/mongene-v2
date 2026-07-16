"""相似比から面積比・表面積比・体積比を求めるまわりの double_solve checker

（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.similar_area_ratio.double_solve")
def double_solve_similar_area_ratio(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.similar_area_ratio")
    return cast(Solution, solver(p["ratio_num"], p["ratio_den"], p["known_area"]))


@register_checker("math.similar_solid_surface_volume_ratio.double_solve")
def double_solve_similar_solid_surface_volume_ratio(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.similar_solid_surface_volume_ratio")
    return cast(Solution, solver(p["ratio_num"], p["ratio_den"]))
