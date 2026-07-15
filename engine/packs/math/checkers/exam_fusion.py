"""exam（入試対策・T1融合）まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.exam_probability_from_counts.double_solve")
def double_solve_exam_probability_from_counts(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.relative_frequency")
    return cast(Solution, solver(p["occurred"], p["total"]))


@register_checker("math.exam_relative_frequency.double_solve")
def double_solve_exam_relative_frequency(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.relative_frequency")
    return cast(Solution, solver(p["occurred"], p["total"]))


@register_checker("math.exam_quartiles_full_summary.double_solve")
def double_solve_exam_quartiles_full_summary(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.quartiles_full_summary")
    return cast(Solution, solver(p["data"]))
