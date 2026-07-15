"""四分位数・箱ひげ図まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.median_value.double_solve")
def double_solve_median_value(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.median_value")
    return cast(Solution, solver(p["data"]))


@register_checker("math.quartiles_iqr.double_solve")
def double_solve_quartiles_iqr(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.quartiles_iqr")
    return cast(Solution, solver(p["data"]))


@register_checker("math.five_number_summary.double_solve")
def double_solve_five_number_summary(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.five_number_summary")
    return cast(Solution, solver(p["data"]))


@register_checker("math.classify_distribution_statistic.double_solve")
def double_solve_classify_distribution_statistic(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.classify_distribution_statistic")
    return cast(Solution, solver(p["concept"]))
