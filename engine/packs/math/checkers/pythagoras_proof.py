"""三平方の定理の証明／その逆の double_solve checker（G-Q1・§6.2）。

答えの証明文は params に入っていないので、checker は **型＋パラメータだけから図を
組み直し、面積の恒等式を検証し直し、式変形をやり直して**、同じ筋道の行の列になるかを
見る（逆のほうは3辺から a² + b² と c² を計算し直す）。recipe の出力は一切見ない。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.pythagoras_area_proof.double_solve")
def double_solve_pythagoras_area_proof(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.pythagoras_area_proof")
    return cast(
        Solution,
        solver(p["proof_id"], p["letters"], p["names"], p["flip"], p["guided"]),
    )


@register_checker("math.pythagoras_converse_proof.double_solve")
def double_solve_pythagoras_converse_proof(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.pythagoras_converse_proof")
    return cast(Solution, solver(p["context"], p["names"], p["triple_index"], p["swap"]))


__all__ = [
    "double_solve_pythagoras_area_proof",
    "double_solve_pythagoras_converse_proof",
]
