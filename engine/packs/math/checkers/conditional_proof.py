"""仮定と結論の証明・反例による否定の double_solve checker（G-Q1・§6.2）。

この form では「独立検証」の意味が数値セルと違う。答え（証明文・反例）も命題の真偽も
params に入っていないので、checker は **型＋パラメータだけから命題を組み直し、真偽を
判定し直し、反例を探し直して**、同じ判断・同じ筋道の行の列になるかを見る。recipe の
出力は一切見ない（`_answers_match` が ProofAnswer を (op, claim, reason) の列で照合する）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.conditional_statement_proof.double_solve")
def double_solve_conditional_statement_proof(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.conditional_statement_proof")
    return cast(Solution, solver(p["prop_id"], p["letters"], p["numbers"], p["mode"]))


__all__ = ["double_solve_conditional_statement_proof"]
