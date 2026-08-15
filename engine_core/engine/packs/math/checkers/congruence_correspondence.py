"""合同な図形の対応関係まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.congruence_transfer_values.double_solve")
def double_solve_congruence_transfer_values(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.congruence_transfer_values")
    return cast(Solution, solver(p["side_value"], p["angle_value"]))


@register_checker("math.congruence_symbol_and_side.double_solve")
def double_solve_congruence_symbol_and_side(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.congruence_symbol_and_side")
    return cast(Solution, solver(p["p_labels"], p["q_labels"], p["i"], p["j"]))


@register_checker("math.congruence_corresponding_pair.double_solve")
def double_solve_congruence_corresponding_pair(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.congruence_corresponding_pair")
    return cast(
        Solution, solver(p["p_labels"], p["q_labels"], p["angle_i"], p["side_i"], p["side_j"])
    )
