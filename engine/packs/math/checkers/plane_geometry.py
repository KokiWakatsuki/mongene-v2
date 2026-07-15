"""平面図形まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.judge_transformation_invariant.double_solve")
def double_solve_judge_transformation_invariant(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_transformation_invariant")
    return cast(Solution, solver(p["topic"]))


@register_checker("math.judge_construction_property.double_solve")
def double_solve_judge_construction_property(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_construction_property")
    return cast(Solution, solver(p["topic"]))


@register_checker("math.judge_circle_property.double_solve")
def double_solve_judge_circle_property(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.judge_circle_property")
    return cast(Solution, solver(p["concept"]))


@register_checker("math.judge_point_line_distance_meaning.double_solve")
def double_solve_judge_point_line_distance_meaning(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.judge_point_line_distance_meaning")
    return cast(Solution, solver("_"))


@register_checker("math.sector_arc_length_or_area.double_solve")
def double_solve_sector_arc_length_or_area(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.sector_arc_length_or_area")
    return cast(Solution, solver(p["radius"], p["angle"], p["target"]))


@register_checker("math.sector_solve_central_angle.double_solve")
def double_solve_sector_solve_central_angle(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.sector_solve_central_angle")
    return cast(Solution, solver(p["radius"], p["area_coeff"]))
