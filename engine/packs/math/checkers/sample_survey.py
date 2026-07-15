"""標本調査まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.sample_ratio_estimate.double_solve")
def double_solve_sample_ratio_estimate(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.sample_ratio_estimate")
    return cast(Solution, solver(p["sample_size"], p["sample_count"], p["population_size"]))


@register_checker("math.sample_ratio_solve_population.double_solve")
def double_solve_sample_ratio_solve_population(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.sample_ratio_solve_population")
    return cast(Solution, solver(p["sample_size"], p["sample_count"], p["known_estimate"]))


@register_checker("math.judge_appropriate_survey_method.double_solve")
def double_solve_judge_appropriate_survey_method(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_appropriate_survey_method")
    return cast(Solution, solver(p["needs_sample"]))


@register_checker("math.judge_sampling_bias.double_solve")
def double_solve_judge_sampling_bias(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_sampling_bias")
    return cast(Solution, solver(p["is_biased"]))


@register_checker("math.explain_sample_ratio_rationale.double_solve")
def double_solve_explain_sample_ratio_rationale(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.explain_sample_ratio_rationale")
    return cast(Solution, solver(p["n"]))
