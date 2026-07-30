"""動点まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.solve_moving_point_area.double_solve")
def double_solve_solve_moving_point_area(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.solve_moving_point_area")
    return cast(Solution, solver(p["s"], p["v"], p["t"], p["mode"]))


@register_checker("math.draw_area_time_graph_segment.double_solve")
def double_solve_draw_area_time_graph_segment(mr: MR) -> Solution:
    # 問題パラメータ（a,b・変域端 seg_x_lo/seg_x_hi・開閉 closed_lo/closed_hi）だけから
    # 端点特徴を再計算する（g2_l23.graph_table の draw_segment と同じ solver を再利用）。
    p = mr.params
    solver = REGISTRY.solver("math.draw_segment_features")
    return cast(Solution, solver(
        sympy.sympify(p["a"]), sympy.sympify(p["b"]),
        sympy.sympify(p["seg_x_lo"]), sympy.sympify(p["seg_x_hi"]),
        bool(p["closed_lo"]), bool(p["closed_hi"]),
    ))


__all__ = ["double_solve_solve_moving_point_area", "double_solve_draw_area_time_graph_segment"]
