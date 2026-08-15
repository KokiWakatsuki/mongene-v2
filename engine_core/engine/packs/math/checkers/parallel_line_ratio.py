"""平行線と線分の比の定理・その逆・中点連結定理まわりの double_solve checker

（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.parallel_segment_ratio_length.double_solve")
def double_solve_parallel_segment_ratio_length(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.parallel_segment_ratio_length")
    return cast(Solution, solver(p["ad"], p["db"], p["de"]))


@register_checker("math.judge_parallel_from_ratio.double_solve")
def double_solve_judge_parallel_from_ratio(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_parallel_from_ratio")
    return cast(Solution, solver(p["ad"], p["db"], p["ae"], p["ec"]))


@register_checker("math.midpoint_connector_length.double_solve")
def double_solve_midpoint_connector_length(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.midpoint_connector_length")
    return cast(Solution, solver(p["bc"]))


@register_checker("math.parallel_lines_transversal_ratio.double_solve")
def double_solve_parallel_lines_transversal_ratio(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.parallel_lines_transversal_ratio")
    return cast(Solution, solver(p["ab"], p["de"], p["ef"]))


@register_checker("math.parallel_ratio_judge_then_length.double_solve")
def double_solve_parallel_ratio_judge_then_length(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.parallel_ratio_judge_then_length")
    return cast(Solution, solver(p["ad"], p["db"], p["ae"], p["ec"], p["de"]))
