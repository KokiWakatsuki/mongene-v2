"""平面図形の移動（平行移動・回転移動・対称移動）の double_solve checker

（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。Lv1(grid_only)/Lv2(coordinate) は
どちらも同じ独立ソルバに委譲する（recipe が given のキー名で level_sep を担保）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.translate_polygon_grid.double_solve")
def double_solve_translate_polygon_grid(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.translate_polygon_features")
    return cast(Solution, solver(p["pts"], p["dx"], p["dy"]))


@register_checker("math.translate_polygon_coordinate.double_solve")
def double_solve_translate_polygon_coordinate(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.translate_polygon_features")
    return cast(Solution, solver(p["pts"], p["dx"], p["dy"]))


@register_checker("math.rotate_polygon_grid.double_solve")
def double_solve_rotate_polygon_grid(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.rotate_polygon_features")
    return cast(Solution, solver(p["pts"], p["center"], p["angle"]))


@register_checker("math.rotate_polygon_coordinate.double_solve")
def double_solve_rotate_polygon_coordinate(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.rotate_polygon_features")
    return cast(Solution, solver(p["pts"], p["center"], p["angle"]))


@register_checker("math.reflect_polygon_grid.double_solve")
def double_solve_reflect_polygon_grid(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.reflect_polygon_features")
    return cast(Solution, solver(p["pts"], p["axis"]))


@register_checker("math.reflect_polygon_coordinate.double_solve")
def double_solve_reflect_polygon_coordinate(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.reflect_polygon_features")
    return cast(Solution, solver(p["pts"], p["axis"]))
