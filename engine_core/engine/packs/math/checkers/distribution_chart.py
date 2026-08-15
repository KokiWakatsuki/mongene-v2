"""分布のグラフ（graph_table）の double_solve checker（G-Q1 が呼ぶ・§6.2）。

checker は MR.params（＝本文に出ている数値と、図を描くための階級の作り方）だけを見て
solver を引き直す。answer は見ない。「かく」セルの度数分布表は生データや度数列から
数え直され、累積・相対度数はいずれも導出値として再計算される。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.read_distribution_chart.double_solve")
def double_solve_read_distribution_chart(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.read_distribution_chart")
    return cast(
        Solution,
        solver(p["frequencies"], p["class_lo"], p["class_width"], p["target_index"], p["unit"]),
    )


@register_checker("math.tabulate_and_draw_histogram.double_solve")
def double_solve_tabulate_and_draw_histogram(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.tabulate_and_draw_histogram")
    # 度数は params の frequencies ではなく**生データから数え直す**（表の作成そのものを検証）。
    return cast(
        Solution,
        solver(p["data"], p["class_lo"], p["class_width"], len(p["frequencies"]), p["unit"]),
    )


@register_checker("math.compare_distribution_shape.double_solve")
def double_solve_compare_distribution_shape(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.compare_distribution_shape")
    return cast(Solution, solver(p["frequencies"], p["frequencies_b"], "A組", "B組"))


@register_checker("math.relative_frequency_polygon.double_solve")
def double_solve_relative_frequency_polygon(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.relative_frequency_polygon")
    return cast(Solution, solver(p["frequencies"], p["class_lo"], p["class_width"], p["unit"]))


@register_checker("math.compare_relative_frequency_chart.double_solve")
def double_solve_compare_relative_frequency_chart(mr: MR) -> Solution:
    p = mr.params
    idx = int(p["target_index"])
    freq_a = [int(v) for v in p["frequencies"]]
    freq_b = [int(v) for v in p["frequencies_b"]]
    solver = REGISTRY.solver("math.compare_relative_frequency")
    return cast(Solution, solver(freq_a[idx], sum(freq_a), freq_b[idx], sum(freq_b)))


@register_checker("math.cumulative_frequency_chart.double_solve")
def double_solve_cumulative_frequency_chart(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.cumulative_frequency_chart")
    return cast(Solution, solver(p["frequencies"], p["class_lo"], p["class_width"], p["unit"]))


@register_checker("math.median_class_from_cumulative.double_solve")
def double_solve_median_class_from_cumulative(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.median_class_from_cumulative")
    return cast(Solution, solver(p["frequencies"], p["class_lo"], p["class_width"], p["unit"]))


@register_checker("math.overlay_frequency_polygons.double_solve")
def double_solve_overlay_frequency_polygons(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.overlay_frequency_polygons")
    return cast(
        Solution,
        solver(
            p["frequencies"], p["frequencies_b"], p["class_lo"], p["class_width"],
            "A組", "B組", p["unit"],
        ),
    )


__all__ = [
    "double_solve_read_distribution_chart",
    "double_solve_tabulate_and_draw_histogram",
    "double_solve_compare_distribution_shape",
    "double_solve_relative_frequency_polygon",
    "double_solve_compare_relative_frequency_chart",
    "double_solve_cumulative_frequency_chart",
    "double_solve_median_class_from_cumulative",
    "double_solve_overlay_frequency_polygons",
]
