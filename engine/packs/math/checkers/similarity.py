"""相似な図形まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.similarity_ratio_transfer.double_solve")
def double_solve_similarity_ratio_transfer(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    return cast(Solution, solver(p["ratio_num"], p["ratio_den"], p["known_side"]))


@register_checker("math.identify_similar_corresponding_vertex.double_solve")
def double_solve_identify_similar_corresponding_vertex(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.identify_similar_corresponding_vertex")
    return cast(Solution, solver(p["labels1"], p["labels2"], p["index"]))


@register_checker("math.similarity_proven_ratio_length.double_solve")
def double_solve_similarity_proven_ratio_length(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    return cast(Solution, solver(p["ratio_num"], p["ratio_den"], p["known_side"]))
