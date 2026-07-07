"""SolveSimilarityVerb（§18.2・相似/線分比/中点連結の長さ算出）

数学核は「比 a:b = c:x を解く（x = b·c/a）」で SolveEqVerb.solve_proportion と同型だが、
narration_hint に**幾何の定理文脈**（相似比・平行線と線分の比・中点連結定理）を明示する。
bare な「比例式を解く」だと MR に幾何文脈が出ず翻訳が題材ズレ（相似レッスンなのに
「18×11 を計算」）になるため、context 別に narration と operation を分ける。

答え（sympy_expr）は moat（SymPy 計算値）で不変。
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

SimilarityContext = Literal[
    "similarity_ratio",     # 相似な図形: 相似比 a:b と対応辺 c から対応辺 x = c·b/a
    "parallel_segments",    # 平行線と線分の比の定理: a:b = c:x → x = b·c/a
    "midpoint_connector",   # 中点連結定理: 底辺 = 中点連結線分 × 2（MN=c → BC=2c）
]


@register_verb
class SolveSimilarityVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["ProportionAtom"]
    tags: ClassVar[List[str]] = ["similarity", "proportion_equation"]

    def __init__(self, context: SimilarityContext = "similarity_ratio") -> None:
        self.context: SimilarityContext = context

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "ProportionAtom 1 つを要求"
        if type(nouns[0]).__name__ not in self.accepted_noun_types:
            return False, f"{type(nouns[0]).__name__} は不可"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        atom = nouns[0]
        symbols = atom.get_symbols()
        a = symbols.get("lhs_a", sympy.Integer(1))
        b = symbols.get("lhs_b", sympy.Integer(1))
        c = symbols.get("rhs_c", sympy.Integer(1))

        if self.context == "midpoint_connector":
            # 中点連結定理: 中点を結ぶ線分 MN=c のとき、底辺 BC = 2·MN
            x_val = sympy.Integer(2) * c
            narration = (
                f"中点連結定理により、中点を結んだ線分の長さが {int(c)} のとき、"
                f"底辺の長さ = {int(c)} × 2 で求める"
            )
            op = "solve_midpoint_connector"
            operands = [f"MN={int(c)}"]
        else:
            # 比 a:b = c:x を解く（x = b·c/a）
            x_val = sympy.Rational(b * c, a) if a != 0 else sympy.Integer(0)
            if self.context == "parallel_segments":
                narration = (
                    f"平行線と線分の比の定理より {int(a)}:{int(b)} = {int(c)}:x が成り立つ。"
                    f"x = {int(b)}×{int(c)}÷{int(a)} で求める"
                )
                op = "solve_parallel_segment_ratio"
            else:  # similarity_ratio
                narration = (
                    f"相似比が {int(a)}:{int(b)} の相似な図形で、対応する辺が {int(c)} のとき、"
                    f"対応する辺 x = {int(c)}×{int(b)}÷{int(a)} で求める"
                )
                op = "solve_similarity_ratio"
            operands = [f"{int(a)}:{int(b)}", f"corr={int(c)}"]

        return LogicStep(
            operation_name=op,
            operands=operands,
            sympy_expr=sympy.simplify(x_val),
            narration_hint=narration,
        )
