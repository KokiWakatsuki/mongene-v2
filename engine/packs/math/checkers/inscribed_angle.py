"""円周角の定理・その逆・弧の比例まわりの double_solve checker

（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.inscribed_angle_from_central.double_solve")
def double_solve_inscribed_angle_from_central(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.inscribed_angle_from_central")
    return cast(Solution, solver(p["central_angle"]))


@register_checker("math.inscribed_angle_transfer_same_arc.double_solve")
def double_solve_inscribed_angle_transfer_same_arc(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.inscribed_angle_transfer_same_arc")
    return cast(Solution, solver(p["v2"]))


@register_checker("math.judge_concyclic_from_angle.double_solve")
def double_solve_judge_concyclic_from_angle(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_concyclic_from_angle")
    return cast(Solution, solver(p["angle_c"], p["angle_d"]))


@register_checker("math.arc_proportional_angle.double_solve")
def double_solve_arc_proportional_angle(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.arc_proportional_angle")
    return cast(Solution, solver(p["multiplier"], p["known_angle"]))


@register_checker("math.inscribed_angle_two_chords_intersection.double_solve")
def double_solve_inscribed_angle_two_chords_intersection(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.inscribed_angle_two_chords_intersection")
    return cast(Solution, solver(p["bac"], p["acd"]))


@register_checker("math.equal_arc_inscribed_angle.double_solve")
def double_solve_equal_arc_inscribed_angle(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.equal_arc_inscribed_angle")
    return cast(
        Solution, solver(p["n"], p["labels"], p["vertex"], p["a"], p["c"])
    )
