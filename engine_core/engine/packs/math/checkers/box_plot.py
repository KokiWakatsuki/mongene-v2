"""箱ひげ図（graph_table）の double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。

「読む」セルの checker は params の `five_number`（＝描画座標）を**使わない**。
図に描かれている目もりの情報（`axis_lo` / `axis_step` / `box_ticks`）だけを solver に
渡し、値をゼロから復元させる。答えを params から読み直すだけの検証にしないため。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.read_box_plot.double_solve")
def double_solve_read_box_plot(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.read_box_plot_values")
    return cast(Solution, solver(p["axis_lo"], p["axis_step"], p["box_ticks"], p["read_target"]))


@register_checker("math.draw_box_plot_from_data.double_solve")
def double_solve_draw_box_plot_from_data(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.draw_box_plot_features")
    return cast(Solution, solver(p["data"]))


@register_checker("math.read_two_box_plots.double_solve")
def double_solve_read_two_box_plots(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.compare_box_plots_center_spread")
    return cast(
        Solution, solver(p["axis_lo"], p["axis_step"], p["box_ticks_a"], p["box_ticks_b"])
    )


@register_checker("math.compare_two_box_plots_iqr.double_solve")
def double_solve_compare_two_box_plots_iqr(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.compare_box_plots_iqr")
    return cast(
        Solution, solver(p["axis_lo"], p["axis_step"], p["box_ticks_a"], p["box_ticks_b"])
    )


@register_checker("math.word_problem_box_plot_compare.double_solve")
def double_solve_word_problem_box_plot_compare(mr: MR) -> list[Solution]:
    """小問と同順の list[Solution]（(1)=中央値・(2)=範囲）を返す（G-Q1 の多段規約）。"""
    p = mr.params
    solver = REGISTRY.solver("math.compare_box_plot_statistic")
    return [
        cast(
            Solution,
            solver(p["axis_lo"], p["axis_step"], p["box_ticks_a"], p["box_ticks_b"], s),
        )
        for s in ("median", "range")
    ]


@register_checker("math.word_problem_box_plot_trend.double_solve")
def double_solve_word_problem_box_plot_trend(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_box_plot_trend_claim")
    return cast(
        Solution, solver(p["axis_lo"], p["axis_step"], p["box_ticks_a"], p["box_ticks_b"])
    )


@register_checker("math.word_problem_box_plot_stability.double_solve")
def double_solve_word_problem_box_plot_stability(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_box_plot_stability_claim")
    return cast(
        Solution, solver(p["axis_lo"], p["axis_step"], p["box_ticks_a"], p["box_ticks_b"])
    )


__all__ = [
    "double_solve_read_box_plot",
    "double_solve_word_problem_box_plot_compare",
    "double_solve_word_problem_box_plot_trend",
    "double_solve_word_problem_box_plot_stability",
    "double_solve_draw_box_plot_from_data",
    "double_solve_read_two_box_plots",
    "double_solve_compare_two_box_plots_iqr",
]


# ---------------------------------------------------------------------------
# exam_l7（入試融合・データの活用）— C13
# ---------------------------------------------------------------------------
@register_checker("math.exam_word_problem_box_plot_guided.double_solve")
def double_solve_exam_word_problem_box_plot_guided(mr: MR) -> list[Solution]:
    """(1)=Aの中央値・(2)=四分位範囲が大きいほう・(3)=傾向の判断。図の目もりから解き直す。"""
    p = mr.params
    lo, step, ta, tb = p["axis_lo"], p["axis_step"], p["box_ticks_a"], p["box_ticks_b"]
    return [
        cast(
            Solution,
            REGISTRY.solver("math.read_box_plot_single_statistic")(lo, step, ta, "median"),
        ),
        cast(
            Solution,
            REGISTRY.solver("math.compare_box_plot_statistic")(lo, step, ta, tb, "iqr"),
        ),
        cast(Solution, REGISTRY.solver("math.judge_box_plot_trend_claim")(lo, step, ta, tb)),
    ]


@register_checker("math.exam_word_problem_box_plot_spread_claim.double_solve")
def double_solve_exam_word_problem_box_plot_spread_claim(mr: MR) -> Solution:
    p = mr.params
    return cast(
        Solution,
        REGISTRY.solver("math.judge_spread_claim_by_two_measures")(
            p["axis_lo"], p["axis_step"], p["box_ticks_a"], p["box_ticks_b"]
        ),
    )
