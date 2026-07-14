"""確率まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.relative_frequency_g1.double_solve")
def double_solve_relative_frequency_g1(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.relative_frequency")
    return cast(Solution, solver(p["occurred"], p["total"]))


@register_checker("math.relative_frequency_g2.double_solve")
def double_solve_relative_frequency_g2(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.relative_frequency")
    return cast(Solution, solver(p["occurred"], p["total"]))


@register_checker("math.probability_single_die.double_solve")
def double_solve_probability_single_die(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.probability_single_die")
    return cast(Solution, solver(p["space_name"], p["condition"], p["target"], p["size"]))


@register_checker("math.probability_two_dice.double_solve")
def double_solve_probability_two_dice(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.probability_two_dice")
    return cast(Solution, solver(p["faces"], p["condition"], p["target"]))


@register_checker("math.probability_ordered_selection.double_solve")
def double_solve_probability_ordered_selection(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.probability_ordered_selection")
    return cast(Solution, solver(p["n"], p["r"], p["target_index"]))


@register_checker("math.probability_combination_selection.double_solve")
def double_solve_probability_combination_selection(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.probability_combination_selection")
    return cast(Solution, solver(p["counts"], p["r"], p["target_color"]))


@register_checker("math.probability_complement.double_solve")
def double_solve_probability_complement(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.probability_complement")
    return cast(Solution, solver(p["p_num"], p["p_den"]))


@register_checker("math.probability_at_least_one.double_solve")
def double_solve_probability_at_least_one(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.probability_at_least_one")
    return cast(Solution, solver(p["space_size"], p["favorable_size"], p["trials"]))


@register_checker("math.judge_equally_likely.double_solve")
def double_solve_judge_equally_likely(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_equally_likely")
    return cast(Solution, solver(p["is_equally_likely"]))


@register_checker("math.interpret_relative_frequency_limit.double_solve")
def double_solve_interpret_relative_frequency_limit(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.interpret_relative_frequency_limit")
    return cast(Solution, solver(None))


__all__ = [
    "double_solve_relative_frequency_g1",
    "double_solve_relative_frequency_g2",
    "double_solve_probability_single_die",
    "double_solve_probability_two_dice",
    "double_solve_probability_ordered_selection",
    "double_solve_probability_combination_selection",
    "double_solve_probability_complement",
    "double_solve_probability_at_least_one",
    "double_solve_judge_equally_likely",
    "double_solve_interpret_relative_frequency_limit",
]
