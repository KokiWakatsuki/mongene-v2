"""文字式による数の性質の説明の double_solve checker（G-Q1・§6.2）。

この form では「独立検証」の意味が数値セルと違う。答え（説明文）は params に
入っていないので、checker は **型＋パラメータだけから命題を組み直し、式変形を
やり直して**、同じ結論・同じ筋道の行の列になるかを見る。recipe の出力は一切
見ない（`_answers_match` が ProofAnswer を (op, claim, reason) の列で照合する）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.number_property_proof.double_solve")
def double_solve_number_property_proof(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.number_property_proof")
    return cast(
        Solution,
        solver(p["prop_id"], p["letters"], p["numbers"], p["guided"]),
    )


__all__ = ["double_solve_number_property_proof"]
