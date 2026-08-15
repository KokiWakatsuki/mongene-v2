"""空間図形の「計量」（表面積・体積）まわりの double_solve checker（C8 横展開9セル）。

いずれも mr.params から "mode" を取り出し、残りを共通ソルバ
`math.solid_figure_measure`（solvers/solid_figure.py）にそのまま渡して独立再計算する。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


def _double_solve(mr: MR) -> Solution:
    p = dict(mr.params)
    mode = p.pop("mode")
    solver = REGISTRY.solver("math.solid_figure_measure")
    return cast(Solution, solver(mode, p))


@register_checker("math.solid_surface_direct.double_solve")
def double_solve_solid_surface_direct(mr: MR) -> Solution:
    return _double_solve(mr)


@register_checker("math.solid_cone_surface_central_angle.double_solve")
def double_solve_solid_cone_surface_central_angle(mr: MR) -> Solution:
    return _double_solve(mr)


@register_checker("math.solid_composite_or_reverse_surface.double_solve")
def double_solve_solid_composite_or_reverse_surface(mr: MR) -> Solution:
    return _double_solve(mr)


@register_checker("math.solid_cylinder_volume_substitution.double_solve")
def double_solve_solid_cylinder_volume_substitution(mr: MR) -> Solution:
    return _double_solve(mr)


@register_checker("math.solid_prism_pyramid_volume_direct.double_solve")
def double_solve_solid_prism_pyramid_volume_direct(mr: MR) -> Solution:
    return _double_solve(mr)


@register_checker("math.solid_right_triangle_volume_multistep.double_solve")
def double_solve_solid_right_triangle_volume_multistep(mr: MR) -> Solution:
    return _double_solve(mr)


@register_checker("math.solid_composite_or_reverse_volume.double_solve")
def double_solve_solid_composite_or_reverse_volume(mr: MR) -> Solution:
    return _double_solve(mr)


@register_checker("math.solid_sphere_direct.double_solve")
def double_solve_solid_sphere_direct(mr: MR) -> Solution:
    return _double_solve(mr)


@register_checker("math.solid_hemisphere_or_reverse.double_solve")
def double_solve_solid_hemisphere_or_reverse(mr: MR) -> Solution:
    return _double_solve(mr)


__all__ = [
    "double_solve_solid_surface_direct",
    "double_solve_solid_cone_surface_central_angle",
    "double_solve_solid_composite_or_reverse_surface",
    "double_solve_solid_cylinder_volume_substitution",
    "double_solve_solid_prism_pyramid_volume_direct",
    "double_solve_solid_right_triangle_volume_multistep",
    "double_solve_solid_composite_or_reverse_volume",
    "double_solve_solid_sphere_direct",
    "double_solve_solid_hemisphere_or_reverse",
]
