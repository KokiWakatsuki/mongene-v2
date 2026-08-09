"""基本作図（form: construction）の double_solve checker（G-Q1 が呼ぶ・§6.2）。

G-Q1 は `f"{mr.provenance.recipe}.double_solve"` で checker を引き、MR の params に
残った「問題を定義する値」——与えられた点・直線・角の座標と記号——だけから独立ソルバで
作図し直す（recipe が構成した答えも図も見ない）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.construct_perpendicular_bisector.double_solve")
def double_solve_construct_perpendicular_bisector(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.perpendicular_bisector_of_segment")
    return cast(Solution, solver(p["ax"], p["ay"], p["bx"], p["by"], p["name_a"], p["name_b"]))


@register_checker("math.construct_equidistant_point_on_line.double_solve")
def double_solve_construct_equidistant_point_on_line(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.equidistant_point_on_line")
    return cast(
        Solution,
        solver(
            p["ax"], p["ay"], p["bx"], p["by"],
            p["lx"], p["ly"], p["ldx"], p["ldy"],
            p["name_a"], p["name_b"],
        ),
    )


@register_checker("math.construct_angle_bisector.double_solve")
def double_solve_construct_angle_bisector(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.angle_bisector_of_angle")
    return cast(
        Solution,
        solver(
            p["ox"], p["oy"], p["ux"], p["uy"], p["vx"], p["vy"],
            p["name_o"], p["name_1"], p["name_2"],
        ),
    )


@register_checker("math.construct_equidistant_point_from_two_sides.double_solve")
def double_solve_construct_equidistant_point_from_two_sides(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.equidistant_point_from_two_sides")
    return cast(
        Solution,
        solver(
            p["ox"], p["oy"], p["ux"], p["uy"], p["vx"], p["vy"],
            p["name_o"], p["name_1"], p["name_2"],
        ),
    )


@register_checker("math.construct_perpendicular.double_solve")
def double_solve_construct_perpendicular(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.perpendicular_through_point")
    return cast(
        Solution,
        solver(p["px"], p["py"], p["lx"], p["ly"], p["ldx"], p["ldy"], p["name_p"]),
    )


@register_checker("math.construct_foot_and_distance.double_solve")
def double_solve_construct_foot_and_distance(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.foot_and_point_line_distance")
    return cast(
        Solution,
        solver(
            p["px"], p["py"], p["lx"], p["ly"], p["ldx"], p["ldy"],
            p["name_p"], p["name_h"],
        ),
    )


@register_checker("math.construct_locus_equidistant_two_points.double_solve")
def double_solve_construct_locus_equidistant_two_points(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.locus_equidistant_two_points")
    return cast(Solution, solver(p["ax"], p["ay"], p["bx"], p["by"], p["name_a"], p["name_b"]))


@register_checker("math.construct_equidistant_point_three.double_solve")
def double_solve_construct_equidistant_point_three(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.circumcenter_of_three_points")
    return cast(
        Solution,
        solver(
            p["ax"], p["ay"], p["bx"], p["by"], p["cx"], p["cy"],
            p["name_a"], p["name_b"], p["name_c"],
        ),
    )


@register_checker("math.construct_point_on_side_equidistant.double_solve")
def double_solve_construct_point_on_side_equidistant(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.point_on_side_equidistant_from_two_sides")
    return cast(
        Solution,
        solver(
            p["ax"], p["ay"], p["ux"], p["uy"], p["vx"], p["vy"],
            p["name_a"], p["name_b"], p["name_c"],
        ),
    )


__all__ = [
    "double_solve_construct_perpendicular_bisector",
    "double_solve_construct_equidistant_point_on_line",
    "double_solve_construct_angle_bisector",
    "double_solve_construct_equidistant_point_from_two_sides",
    "double_solve_construct_perpendicular",
    "double_solve_construct_foot_and_distance",
    "double_solve_construct_locus_equidistant_two_points",
    "double_solve_construct_equidistant_point_three",
    "double_solve_construct_point_on_side_equidistant",
]
