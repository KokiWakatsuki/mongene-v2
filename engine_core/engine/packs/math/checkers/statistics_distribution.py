"""度数分布・代表値まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.frequency_table_value.double_solve")
def double_solve_frequency_table_value(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.frequency_table_value")
    return cast(Solution, solver(p["class_start"], p["class_width"], p["frequencies"], p["target_index"]))


@register_checker("math.relative_frequency_stats_single.double_solve")
def double_solve_relative_frequency_stats_single(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.relative_frequency")
    return cast(Solution, solver(p["occurred"], p["total"]))


@register_checker("math.compare_relative_frequency.double_solve")
def double_solve_compare_relative_frequency(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.compare_relative_frequency")
    return cast(Solution, solver(p["freq_a"], p["total_a"], p["freq_b"], p["total_b"]))


@register_checker("math.cumulative_frequency_value.double_solve")
def double_solve_cumulative_frequency_value(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.cumulative_frequency_value")
    return cast(Solution, solver(p["frequencies"], p["target_index"]))


@register_checker("math.cumulative_relative_frequency_and_complement.double_solve")
def double_solve_cumulative_relative_frequency_and_complement(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.cumulative_relative_frequency_and_complement")
    return cast(Solution, solver(p["frequencies"], p["target_index"]))


@register_checker("math.representative_values_raw.double_solve")
def double_solve_representative_values_raw(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.representative_values_raw")
    return cast(Solution, solver(p["data"]))


@register_checker("math.mean_from_grouped_table.double_solve")
def double_solve_mean_from_grouped_table(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.mean_from_grouped_table")
    return cast(Solution, solver(p["class_start"], p["class_width"], p["frequencies"]))


@register_checker("math.judge_appropriate_representative_value.double_solve")
def double_solve_judge_appropriate_representative_value(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_appropriate_representative_value")
    return cast(Solution, solver(p["has_outliers"]))
