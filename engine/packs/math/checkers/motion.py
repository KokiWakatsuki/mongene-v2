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


@register_checker("math.word_problem_moving_points_area.double_solve")
def double_solve_word_problem_moving_points_area(mr: MR) -> list[Solution]:
    """小問と同順の list[Solution]（(1)=面積の式・(2)=時刻）を返す（G-Q1 の多段規約）。

    渡すのは `numbers`＝**本文に出ている数値だけ**（速さ・与えられた面積）。
    答えの時刻も面積の式も params に無いので、解き直しが答えの読み直しにならない。
    1辺は面積の式にも時刻にも効かない（P・Q が辺の上にいる間の話）ので渡さない。
    """
    n = mr.params["numbers"]
    return [
        cast(Solution, REGISTRY.solver("math.express_moving_points_area")(n["speed"])),
        cast(
            Solution,
            REGISTRY.solver("math.solve_moving_points_area_time")(n["speed"], n["area"]),
        ),
    ]


@register_checker("math.word_problem_moving_point_all_times.double_solve")
def double_solve_word_problem_moving_point_all_times(mr: MR) -> Solution:
    n = mr.params["numbers"]
    solver = REGISTRY.solver("math.solve_moving_point_area_all_times")
    return cast(Solution, solver(n["side"], n["speed"], n["area"]))


@register_checker("math.word_problem_area_graph_and_times.double_solve")
def double_solve_word_problem_area_graph_and_times(mr: MR) -> list[Solution]:
    """小問と同順の list[Solution]（(1)=グラフの折れ点・(2)=時刻）を返す。

    渡すのは `numbers`＝本文に出ている数値（1辺・速さ・面積）だけ。折れ点の座標も
    答えの時刻も params に無いので、解き直しが答えの読み直しにならない。
    """
    n = mr.params["numbers"]
    return [
        cast(
            Solution,
            REGISTRY.solver("math.draw_three_interval_area_graph_features")(
                n["side"], n["speed"]
            ),
        ),
        cast(
            Solution,
            REGISTRY.solver("math.solve_moving_point_area_all_times")(
                n["side"], n["speed"], n["area"]
            ),
        ),
    ]


__all__ = [
    "double_solve_solve_moving_point_area",
    "double_solve_word_problem_area_graph_and_times",
    "double_solve_draw_area_time_graph_segment",
    "double_solve_word_problem_moving_points_area",
    "double_solve_word_problem_moving_point_all_times",
]
