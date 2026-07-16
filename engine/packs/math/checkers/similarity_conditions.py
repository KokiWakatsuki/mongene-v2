"""三角形の相似条件まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.similar_triangle_x_shape.double_solve")
def double_solve_similar_triangle_x_shape(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.similar_triangle_x_shape")
    return cast(Solution, solver(p["oa"], p["ob"], p["oc"]))


@register_checker("math.identify_similarity_condition.double_solve")
def double_solve_identify_similarity_condition(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.identify_similarity_condition")
    return cast(Solution, solver(p["condition_key"]))
