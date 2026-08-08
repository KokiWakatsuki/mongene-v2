"""相似比から面積比・表面積比・体積比を求めるまわりの double_solve checker

（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.similar_area_ratio.double_solve")
def double_solve_similar_area_ratio(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.similar_area_ratio")
    return cast(Solution, solver(p["ratio_num"], p["ratio_den"], p["known_area"]))


@register_checker("math.similar_solid_surface_volume_ratio.double_solve")
def double_solve_similar_solid_surface_volume_ratio(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.similar_solid_surface_volume_ratio")
    return cast(Solution, solver(p["ratio_num"], p["ratio_den"]))


@register_checker("math.similar_triangle_trapezoid_area_ratio.double_solve")
def double_solve_similar_triangle_trapezoid_area_ratio(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.similar_triangle_trapezoid_area_ratio")
    return cast(Solution, solver(p["ad"], p["db"]))


@register_checker("math.similar_solid_ratio_from_volume.double_solve")
def double_solve_similar_solid_ratio_from_volume(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.similar_solid_ratio_from_volume")
    return cast(Solution, solver(p["vol_p"], p["vol_q"]))


# ---------------------------------------------------------------------------
# exam_l6（入試融合・相似と面積比／体積比）— C13
#
# 独立性: params が持つのは**場面文に出ている数値**（相似比・体積・辺の長さ）だけで、
# 答え（比・面積）は入っていない。checker は recipe と共有する EXAM_L6_SOLVERS で
# その数値から解き直す（word_problem_probability.py の double_solve と同じ設計）。
# ---------------------------------------------------------------------------
def _double_solve_exam_l6(mr: MR) -> list[Solution]:
    from engine.packs.math.recipes.similarity_scale_ratio import EXAM_L6_SOLVERS

    return EXAM_L6_SOLVERS[str(mr.params["kind"])](dict(mr.params["numbers"]))


@register_checker("math.exam_similar_solid_volume.double_solve")
def double_solve_exam_similar_solid_volume(mr: MR) -> list[Solution]:
    return _double_solve_exam_l6(mr)


@register_checker("math.exam_cone_split_volume_ratio.double_solve")
def double_solve_exam_cone_split_volume_ratio(mr: MR) -> list[Solution]:
    return _double_solve_exam_l6(mr)


@register_checker("math.exam_parallel_line_area_guided.double_solve")
def double_solve_exam_parallel_line_area_guided(mr: MR) -> list[Solution]:
    return _double_solve_exam_l6(mr)


@register_checker("math.exam_trapezoid_diagonal_ratios.double_solve")
def double_solve_exam_trapezoid_diagonal_ratios(mr: MR) -> list[Solution]:
    return _double_solve_exam_l6(mr)
